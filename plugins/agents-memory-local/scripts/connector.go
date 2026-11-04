// Dependency-free first connection, local setup form, and MCP transport.
// Memory behavior remains in the separately verified binary core.
package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const version = "1.0.7"
const coreHash = "3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34"
const coreBase = "https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/eb80f6277f6d712a89e854f0f54b7067a9bfc9cc/files/"

var helperHash = "e692f9f4edc323c455e019223194b5bbbe3e32d563f071e743a91be084cd48d9"

// Some clients cache the first tools/list result and ignore later refreshes.
// Register the stable core contract immediately; calls stay gated on actual readiness.
//
//go:embed memory-tools.json
var memoryTools []byte

//go:embed memory-use.txt
var memoryUseInstructions string
var prefix, cache, project, helper string
var worker bool
var httpClient = &http.Client{Timeout: 10 * time.Minute}

type status struct {
	Ready   bool              `json:"ready"`
	State   string            `json:"state"`
	Message string            `json:"message"`
	URL     string            `json:"setup_url,omitempty"`
	Version string            `json:"version"`
	Logs    map[string]string `json:"logs,omitempty"`
	Scope   map[string]string `json:"memory_scope,omitempty"`
}
type route struct{ Provider, Host, Model, Key string }
type request struct {
	Project string `json:"project"`
}

func random() string {
	b := make([]byte, 24)
	if _, e := rand.Read(b); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b)
}
func hash(b []byte) string { v := sha256.Sum256(b); return hex.EncodeToString(v[:]) }
func privateDir(p string) error {
	if e := os.MkdirAll(p, 0700); e != nil {
		return e
	}
	for q := p; q != filepath.Dir(q); q = filepath.Dir(q) {
		s, e := os.Lstat(q)
		if e != nil || s.Mode()&os.ModeSymlink != 0 {
			return errors.New("configuration path contains a symbolic link")
		}
	}
	s, e := os.Stat(p)
	if e != nil {
		return e
	}
	st, ok := s.Sys().(*syscall.Stat_t)
	if !s.IsDir() || s.Mode().Perm()&0077 != 0 || !ok || int(st.Uid) != os.Getuid() {
		return errors.New("private setup directory ownership/permissions are invalid")
	}
	return nil
}
func privateRead(p string) ([]byte, error) {
	s, e := os.Lstat(p)
	if e != nil {
		return nil, e
	}
	st, ok := s.Sys().(*syscall.Stat_t)
	if !s.Mode().IsRegular() || s.Mode().Perm()&0077 != 0 || s.Size() > 2<<20 || !ok || int(st.Uid) != os.Getuid() || st.Nlink != 1 {
		return nil, errors.New("private configuration ownership/permissions are invalid")
	}
	return os.ReadFile(p)
}
func atomic(p string, v any) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	if e = privateDir(filepath.Dir(p)); e != nil {
		return e
	}
	if _, e = os.Lstat(p); e == nil {
		if _, e = privateRead(p); e != nil {
			return e
		}
	} else if !os.IsNotExist(e) {
		return e
	}
	tmp := p + "." + random() + ".tmp"
	defer os.Remove(tmp)
	f, e := os.OpenFile(tmp, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	_, e = f.Write(b)
	if e == nil {
		e = f.Sync()
	}
	ce := f.Close()
	if e == nil {
		e = ce
	}
	if e != nil {
		return e
	}
	return os.Rename(tmp, p)
}
func decode(p string, v any) error {
	b, e := privateRead(p)
	if e != nil {
		return e
	}
	return json.Unmarshal(b, v)
}
func statePath(p string) string     { return filepath.Join(cache, "state-"+hash([]byte(p))+".json") }
func writeState(p string, s status) { s.Version = version; _ = atomic(statePath(p), s) }
func global(s status)               { s.Version = version; _ = atomic(filepath.Join(cache, "worker.json"), s) }
func current() status {
	var s status
	if decode(statePath(project), &s) == nil && s.Version == version && s.State != "pending" {
		return s
	}
	if decode(filepath.Join(cache, "worker.json"), &s) == nil && s.Version == version {
		return s
	}
	return status{State: "pending", Message: "로컬 메모리를 준비하고 있습니다.", Version: version}
}
func lock(name string) (*os.File, error) {
	p := filepath.Join(cache, name)
	if _, e := os.Lstat(p); e == nil {
		if _, e = privateRead(p); e != nil {
			return nil, e
		}
	} else if !os.IsNotExist(e) {
		return nil, e
	}
	f, e := os.OpenFile(p, os.O_CREATE|os.O_RDWR|syscall.O_NOFOLLOW, 0600)
	if e != nil {
		return nil, e
	}
	if e = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		f.Close()
		return nil, e
	}
	return f, nil
}
func launchWorker() {
	f, e := lock("worker.lock")
	if e != nil {
		return
	}
	f.Close()
	global(status{State: "checking", Message: "저장된 설정과 로컬 실행 환경을 확인하고 있습니다."})
	self, e := os.Executable()
	if e != nil {
		return
	}
	log, e := os.OpenFile(filepath.Join(cache, "setup.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND|syscall.O_NOFOLLOW, 0600)
	if e != nil {
		return
	}
	defer log.Close()
	cmd := exec.Command(self, "--worker", "--prefix", prefix, "--cache", cache, "--helper", helper)
	cmd.Stdout = log
	cmd.Stderr = log
	cmd.Stdin = nil
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if cmd.Start() == nil {
		_ = cmd.Process.Release()
	}
}
func command(env []string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, args[0], args[1:]...)
	cmd.Env = env
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
func fetch(u, p string) error {
	parsed, e := url.Parse(u)
	if e != nil || parsed.Scheme != "https" {
		return errors.New("HTTPS download is required")
	}
	req, e := http.NewRequest("GET", u, nil)
	if e != nil {
		return e
	}
	req.Header.Set("User-Agent", "agents-memory-local/"+version)
	resp, e := httpClient.Do(req)
	if e != nil {
		return errors.New("download could not connect; check the network and retry")
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("download returned HTTP %d", resp.StatusCode)
	}
	f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	defer f.Close()
	_, e = io.Copy(f, io.LimitReader(resp.Body, 300<<20))
	return e
}
func installed() bool {
	var product map[string]any
	if decode(filepath.Join(prefix, "PRODUCT.json"), &product) != nil || product["product"] != "agents-memory-hindsight-local" {
		return false
	}
	var ready map[string]any
	if decode(filepath.Join(prefix, "current/READY.json"), &ready) != nil || ready["version"] != "1.0.2" {
		return false
	}
	_, e := os.Stat(filepath.Join(prefix, "current/venv/bin/python"))
	return e == nil
}
func loadRoute() (route, bool, error) {
	var p map[string]any
	e := decode(filepath.Join(prefix, "settings/profile.json"), &p)
	if os.IsNotExist(e) {
		return route{}, false, nil
	}
	if e != nil {
		return route{}, false, e
	}
	r := route{}
	r.Provider, _ = p["provider"].(string)
	r.Host, _ = p["subscription_host"].(string)
	r.Model, _ = p["model"].(string)
	if r.Provider == "local-llm" {
		if r.Host == "" {
			r.Host = "codex"
		}
		if r.Host != "claude" && r.Host != "codex" {
			return r, false, errors.New("existing provider settings need review")
		}
		return r, true, nil
	}
	if r.Provider != "jev" {
		return r, false, errors.New("existing provider settings need review")
	}
	var k map[string]any
	e = decode(filepath.Join(prefix, "settings/jev-credential.json"), &k)
	if os.IsNotExist(e) {
		return r, false, nil
	}
	if e != nil {
		return r, false, e
	}
	key, ok := k["api_key"].(string)
	if !ok || key == "" {
		return r, false, errors.New("saved Jev credential needs review")
	}
	return r, true, nil
}

func apiReady() bool {
	var profile struct {
		Port int `json:"api_port"`
	}
	if decode(filepath.Join(prefix, "settings/profile.json"), &profile) != nil {
		return false
	}
	client := &http.Client{Timeout: 2 * time.Second}
	response, e := client.Get(fmt.Sprintf("http://127.0.0.1:%d/health/ready", profile.Port))
	if e != nil {
		return false
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 8192))
	return response.StatusCode == 200
}

const page = `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Agents Memory 설정</title><style>body{font:17px system-ui;background:#f6f7f9;color:#20262e;max-width:520px;margin:10vh auto;padding:24px}main{background:white;padding:32px;border-radius:18px}h1{font-size:26px}label{display:block;margin-top:22px}select,input,button{font:inherit;box-sizing:border-box;width:100%;padding:12px;margin-top:8px;border:1px solid #adb5bf;border-radius:8px}button{background:#1764c0;color:white;border:0;cursor:pointer}small{color:#536171}#message{white-space:pre-wrap}input:focus,select:focus,button:focus{outline:3px solid #8ac2ff}</style><main><h1>기억을 저장할 준비</h1><p>저장 여부를 판단할 LLM을 한 번 선택해 주세요. 설정은 업데이트 후에도 유지됩니다.</p><form id="form"><label>사용할 LLM<select name="provider" id="provider"><option value="jev">Jev</option><option value="claude">구독 Claude · 추천 Sonnet 5.5</option><option value="codex">구독 Codex · 추천 6.1 Terra</option></select></label><label id="keylabel">Jev API 키<input name="key" type="password" autocomplete="off" spellcheck="false" maxlength="4096"></label><small>키는 이 PC에만 저장됩니다. Claude·Codex는 기존 CLI 로그인을 사용합니다.</small><button>저장하고 시작</button></form><p role="status" id="message">설정 확인 중…</p></main><script>const f=document.querySelector('form'),p=document.querySelector('#provider'),m=document.querySelector('#message');p.onchange=()=>document.querySelector('#keylabel').hidden=p.value!=='jev';f.onsubmit=async e=>{e.preventDefault();const b=f.querySelector('button');b.disabled=true;try{const r=await fetch(location.pathname+'configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(f)))});f.key.value='';if(!r.ok){m.textContent=await r.text();b.disabled=false;return}f.hidden=true;m.textContent='설정을 저장했습니다. 설치를 진행하고 있습니다.'}catch(e){m.textContent='연결을 다시 확인해 주세요.';b.disabled=false}};async function poll(){try{const r=await fetch(location.pathname+'status');const s=await r.json();m.textContent=s.message;if(s.state!=='needs_configuration')f.hidden=true;if(s.ready){m.textContent='준비가 끝났습니다. 이 창을 닫고 사용하던 앱으로 돌아가세요.';return}}catch(e){}setTimeout(poll,1500)}poll()</script></html>`

func choose(saved route) (route, func(), error) {
	listener, e := net.Listen("tcp4", "127.0.0.1:0")
	if e != nil {
		return route{}, nil, e
	}
	token := random()
	base := "/" + token + "/"
	origin := "http://" + listener.Addr().String()
	address := origin + base
	chosen := make(chan route, 1)
	var submitted sync.Once
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'")
		if r.Host != listener.Addr().String() || !strings.HasPrefix(r.URL.Path, base) || r.URL.RawQuery != "" {
			http.Error(w, "Not found", 404)
			return
		}
		switch r.URL.Path {
		case base:
			if r.Method != "GET" {
				http.Error(w, "Method not allowed", 405)
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			io.WriteString(w, page)
		case base + "status":
			if r.Method != "GET" {
				http.Error(w, "Method not allowed", 405)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			var s status
			_ = decode(filepath.Join(cache, "worker.json"), &s)
			json.NewEncoder(w).Encode(s)
		case base + "configure":
			if r.Method != "POST" || r.Header.Get("Origin") != origin || r.Header.Get("Content-Type") != "application/json" {
				http.Error(w, "Request refused", 403)
				return
			}
			r.Body = http.MaxBytesReader(w, r.Body, 8192)
			var body struct {
				Provider string `json:"provider"`
				Key      string `json:"key"`
			}
			dec := json.NewDecoder(r.Body)
			dec.DisallowUnknownFields()
			if dec.Decode(&body) != nil {
				http.Error(w, "입력을 확인하세요.", 400)
				return
			}
			next := route{}
			switch body.Provider {
			case "jev":
				next.Provider = "jev"
				next.Model = "jev-1.14.0"
				next.Key = body.Key
				if len(next.Key) < 1 || len(next.Key) > 4096 {
					http.Error(w, "Jev 키를 입력하세요.", 400)
					return
				}
				for _, c := range next.Key {
					if c < 33 || c > 126 {
						http.Error(w, "공백 없는 Jev 키를 입력하세요.", 400)
						return
					}
				}
			case "claude", "codex":
				next.Provider = "local-llm"
				next.Host = body.Provider
				next.Model = map[string]string{"claude": "claude-sonnet-5-5", "codex": "gpt-6.1-terra"}[next.Host]
				if _, e := exec.LookPath(next.Host); e != nil {
					http.Error(w, "선택한 CLI를 설치하고 로그인한 다음 다시 눌러 주세요.", 400)
					return
				}
			default:
				http.Error(w, "LLM을 선택하세요.", 400)
				return
			}
			if saved.Provider != "" && (next.Provider != saved.Provider || next.Host != saved.Host) {
				http.Error(w, "저장된 LLM 설정을 유지해야 합니다.", 409)
				return
			}
			if saved.Model != "" {
				next.Model = saved.Model
			}
			sent := false
			submitted.Do(func() { chosen <- next; sent = true })
			if !sent {
				http.Error(w, "이미 설정을 저장했습니다.", 409)
				return
			}
			w.WriteHeader(202)
		default:
			http.NotFound(w, r)
		}
	})
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16384}
	go server.Serve(listener)
	closeServer := func() { _ = server.Close() }
	global(status{State: "needs_configuration", Message: "브라우저에서 사용할 LLM을 한 번 선택해 주세요. Jev를 선택하면 키를 입력합니다.", URL: address})
	if runtime.GOOS == "darwin" {
		_ = exec.Command("/usr/bin/open", address).Run()
	}
	select {
	case r := <-chosen:
		return r, closeServer, nil
	case <-time.After(30 * time.Minute):
		closeServer()
		return route{}, nil, errors.New("setup form expired; reconnect MCP to retry")
	}
}

func install(r route) error {
	b, e := os.ReadFile(helper)
	if e != nil || hash(b) != helperHash {
		return errors.New("connector helper integrity check failed; update the plugin")
	}
	if installed() {
		return nil
	}
	global(status{State: "downloading", Message: "실행 환경과 E5 검색 임베딩을 다운로드하고 있습니다. 처음 한 번만 필요합니다."})
	work, e := os.MkdirTemp(cache, "download-")
	if e != nil {
		return e
	}
	defer os.RemoveAll(work)
	archive := filepath.Join(work, "core.tar.gz")
	out, e := os.OpenFile(archive, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	for n := 0; n < 19; n++ {
		name := fmt.Sprintf("agents-memory-hindsight-local-1.0.2.tar.gz.part-%03d", n)
		p := filepath.Join(work, name)
		if e = fetch(coreBase+name, p); e != nil {
			out.Close()
			return e
		}
		in, e := os.Open(p)
		if e != nil {
			out.Close()
			return e
		}
		_, e = io.Copy(out, in)
		in.Close()
		os.Remove(p)
		if e != nil {
			out.Close()
			return e
		}
	}
	out.Close()
	in, e := os.Open(archive)
	if e != nil {
		return e
	}
	digest := sha256.New()
	_, e = io.Copy(digest, in)
	in.Close()
	if e != nil || hex.EncodeToString(digest.Sum(nil)) != coreHash {
		return errors.New("memory core integrity verification failed")
	}
	if e = command(os.Environ(), "tar", "-xzf", archive, "-C", work); e != nil {
		return errors.New("could not unpack the verified memory core")
	}
	bundle := filepath.Join(work, "agents-memory-hindsight-local-1.0.2")
	boot := filepath.Join(work, "bootstrap")
	if e = os.Mkdir(boot, 0700); e != nil {
		return e
	}
	target := "darwin-arm64"
	if runtime.GOOS == "linux" {
		target = "linux-x86_64"
	}
	if e = command(os.Environ(), "tar", "-xzf", filepath.Join(bundle, "runtimes", target+".tar.gz"), "-C", boot); e != nil {
		return errors.New("could not unpack bundled Python")
	}
	args := []string{filepath.Join(boot, "python/bin/python3"), "-I", filepath.Join(bundle, "installer.py"), "--bundle", bundle, "--prefix", prefix}
	_, existingProfile := os.Stat(filepath.Join(prefix, "settings/profile.json"))
	if os.IsNotExist(existingProfile) {
		args = append(args, "--provider", r.Provider, "--model", r.Model)
	}
	if os.IsNotExist(existingProfile) && r.Provider == "local-llm" {
		args = append(args, "--host", r.Host)
	}
	if runtime.GOOS == "linux" {
		args = append(args, "--virtual-linux")
	}
	env := os.Environ()
	if r.Key != "" {
		env = append(env, "HINDSIGHT_API_MEMORY_ADMISSION_API_KEY="+r.Key)
	}
	global(status{State: "installing", Message: "실행 환경을 설치하고 있습니다. 잠시 기다려 주세요."})
	if e = command(env, args...); e != nil {
		return errors.New("memory core installation failed; see the private setup log")
	}
	return nil
}

func runWorker() error {
	f, e := lock("worker.lock")
	if e != nil {
		return nil
	}
	defer f.Close()
	if runtime.GOOS == "darwin" {
		v, err := exec.Command("/usr/bin/sw_vers", "-productVersion").Output()
		major, parseErr := strconv.Atoi(strings.Split(strings.TrimSpace(string(v)), ".")[0])
		if err != nil || parseErr != nil || major < 15 {
			return errors.New("자동 로컬 DB에는 macOS 15 이상이 필요합니다. 기존 DB와 설정은 보존했습니다")
		}
	}
	global(status{State: "checking", Message: "저장된 설정과 로컬 실행 환경을 확인하고 있습니다."})
	var service map[string]any
	if decode(filepath.Join(prefix, "settings/mcp-service.json"), &service) == nil && service["enabled"] == false {
		global(status{State: "explicitly_stopped", Message: "사용자가 중지한 상태입니다. am-mcp start로 다시 시작할 수 있습니다."})
		return nil
	}
	r, complete, e := loadRoute()
	if e != nil {
		return e
	}
	closePage := func() {}
	if !complete {
		r, closePage, e = choose(r)
		if e != nil {
			return e
		}
	}
	defer closePage()
	if e = install(r); e != nil {
		return e
	}
	if r.Key != "" {
		var product map[string]any
		if decode(filepath.Join(prefix, "PRODUCT.json"), &product) != nil || product["product"] != "agents-memory-hindsight-local" {
			return errors.New("installation identity is invalid")
		}
		if e = atomic(filepath.Join(prefix, "settings/jev-credential.json"), map[string]any{"schema_version": 1, "api_key": r.Key}); e != nil {
			return e
		}
		r.Key = ""
	}
	idle := 0
	failed := false
	for idle < 10 {
		names, e := filepath.Glob(filepath.Join(cache, "request-*.json"))
		if e != nil {
			return e
		}
		if len(names) == 0 {
			idle++
			time.Sleep(500 * time.Millisecond)
			continue
		}
		idle = 0
		for _, name := range names {
			var req request
			if e = decode(name, &req); e != nil {
				return e
			}
			p, e := filepath.EvalSymlinks(req.Project)
			if e != nil || p != req.Project || p == filepath.Dir(p) {
				return errors.New("project path is invalid")
			}
			writeState(p, status{State: "preparing", Message: "로컬 DB와 프로젝트 기억 저장소를 자동으로 준비하고 있습니다."})
			global(status{State: "preparing", Message: "로컬 DB와 API를 준비하고 있습니다. Docker 설치는 필요하지 않습니다."})
			args := []string{filepath.Join(prefix, "current/venv/bin/python"), "-I", helper, "--prefix", prefix, "setup", "--project", p, "--client", "connector"}
			if runtime.GOOS == "linux" {
				args = append(args, "--virtual-linux", "--no-start")
			}
			environment := []string{}
			for _, value := range os.Environ() {
				if !strings.HasPrefix(value, "DATABASE_URL=") {
					environment = append(environment, value)
				}
			}
			if e = command(environment, args...); e != nil {
				writeState(p, status{State: "setup_failed", Message: "로컬 준비에 실패했습니다. setup.log에서 오류 단계를 확인한 뒤 MCP를 다시 연결하세요."})
				failed = true
				_ = os.Remove(name)
				continue
			}
			if runtime.GOOS == "linux" && !apiReady() {
				cmd := exec.Command(filepath.Join(prefix, "bin/am-mcp"), "service-run")
				cmd.Stdout = os.Stdout
				cmd.Stderr = os.Stderr
				cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
				if e = cmd.Start(); e != nil {
					return e
				}
				_ = cmd.Process.Release()
			}
			deadline := time.Now().Add(150 * time.Second)
			ok := false
			for time.Now().Before(deadline) {
				var profile struct {
					Port int `json:"api_port"`
				}
				if decode(filepath.Join(prefix, "settings/profile.json"), &profile) == nil {
					client := &http.Client{Timeout: 2 * time.Second}
					resp, e := client.Get(fmt.Sprintf("http://127.0.0.1:%d/health/ready", profile.Port))
					if e == nil {
						io.Copy(io.Discard, io.LimitReader(resp.Body, 8192))
						resp.Body.Close()
						if resp.StatusCode == 200 {
							ok = true
							break
						}
					}
				}
				time.Sleep(500 * time.Millisecond)
			}
			if !ok {
				writeState(p, status{State: "api_not_ready", Message: "로컬 API가 준비되지 않았습니다. 비공개 서비스 로그를 확인하세요."})
				failed = true
				_ = os.Remove(name)
				continue
			}
			writeState(p, status{Ready: true, State: "ready", Message: "준비가 끝났습니다. 메모리 도구를 사용할 수 있습니다."})
			os.Remove(name)
		}
	}
	if failed {
		global(status{State: "setup_failed", Message: "일부 프로젝트 준비에 실패했습니다. setup_status와 비공개 로그를 확인하고 MCP를 다시 연결하세요."})
	} else {
		global(status{Ready: true, State: "ready", Message: "준비가 끝났습니다. 사용하던 앱으로 돌아가세요."})
	}
	time.Sleep(3 * time.Second)
	return nil
}

type rpc struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   json.RawMessage `json:"error,omitempty"`
}
type backend struct {
	cmd      *exec.Cmd
	input    io.WriteCloser
	mu       sync.Mutex
	sequence int
	pending  map[string]chan rpc
	done     chan struct{}
}

func (b *backend) call(method string, params any) (json.RawMessage, error) {
	return b.callContext(context.Background(), method, params)
}
func (b *backend) callContext(ctx context.Context, method string, params any) (json.RawMessage, error) {
	b.mu.Lock()
	b.sequence++
	id := fmt.Sprintf("bridge-%d", b.sequence)
	ch := make(chan rpc, 1)
	b.pending[id] = ch
	message := map[string]any{"jsonrpc": "2.0", "id": id, "method": method, "params": params}
	data, _ := json.Marshal(message)
	_, e := b.input.Write(append(data, '\n'))
	b.mu.Unlock()
	if e != nil {
		return nil, e
	}
	defer func() { b.mu.Lock(); delete(b.pending, id); b.mu.Unlock() }()
	select {
	case <-ctx.Done():
		b.mu.Lock()
		data, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "method": "notifications/cancelled", "params": map[string]any{"requestId": id}})
		_, _ = b.input.Write(append(data, '\n'))
		b.mu.Unlock()
		return nil, ctx.Err()
	case r := <-ch:
		if len(r.Error) > 0 {
			return nil, errors.New("memory API call failed")
		}
		return r.Result, nil
	case <-b.done:
		return nil, errors.New("memory transport closed")
	case <-time.After(180 * time.Second):
		return nil, errors.New("memory API call timed out")
	}
}
func openBackend() (*backend, error) {
	cmd := exec.Command(filepath.Join(prefix, "current/venv/bin/python"), "-I", helper, "--prefix", prefix, "proxy", "--transport-only", "--project", project)
	cmd.Stderr = os.Stderr
	input, e := cmd.StdinPipe()
	if e != nil {
		return nil, e
	}
	output, e := cmd.StdoutPipe()
	if e != nil {
		return nil, e
	}
	if e = cmd.Start(); e != nil {
		return nil, e
	}
	b := &backend{cmd: cmd, input: input, pending: map[string]chan rpc{}, done: make(chan struct{})}
	go func() {
		defer close(b.done)
		scanner := bufio.NewScanner(output)
		scanner.Buffer(make([]byte, 4096), 4<<20)
		for scanner.Scan() {
			var r rpc
			if json.Unmarshal(scanner.Bytes(), &r) != nil {
				continue
			}
			var id string
			if json.Unmarshal(r.ID, &id) != nil {
				continue
			}
			b.mu.Lock()
			ch := b.pending[id]
			b.mu.Unlock()
			if ch != nil {
				select {
				case ch <- r:
				default:
				}
			}
		}
		_ = cmd.Wait()
	}()
	_, e = b.call("initialize", map[string]any{"protocolVersion": "2025-11-25", "capabilities": map[string]any{}, "clientInfo": map[string]any{"name": "agents-memory-connector", "version": version}})
	if e != nil {
		b.close()
		return nil, e
	}
	b.mu.Lock()
	_, e = b.input.Write([]byte("{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}\n"))
	b.mu.Unlock()
	if e != nil {
		b.close()
		return nil, e
	}
	return b, nil
}
func (b *backend) close() {
	_ = b.input.Close()
	if b.cmd.Process != nil {
		_ = b.cmd.Process.Kill()
	}
}
func setupTool() any {
	return map[string]any{"name": "setup_status", "description": "Show automatic local setup progress and the local settings page. Never request API keys in chat.", "inputSchema": map[string]any{"type": "object", "properties": map[string]any{}, "additionalProperties": false}}
}
func serve() error {
	home, _ := os.UserHomeDir()
	home, _ = filepath.EvalSymlinks(home)
	if project == home || project == filepath.Dir(project) {
		writeState(project, status{State: "choose_project", Message: "홈 폴더 대신 실제 작업 프로젝트에서 MCP를 연결해 주세요."})
	} else {
		_ = atomic(filepath.Join(cache, "request-"+hash([]byte(project))+".json"), request{project})
		writeState(project, status{State: "pending", Message: "연결을 준비하고 있습니다."})
		launchWorker()
	}
	var out sync.Mutex
	send := func(v any) { out.Lock(); defer out.Unlock(); _ = json.NewEncoder(os.Stdout).Encode(v) }
	var bridge *backend
	var mu sync.RWMutex
	ctx, cancelAll := context.WithCancel(context.Background())
	defer cancelAll()
	pending := map[string]context.CancelFunc{}
	var requests sync.WaitGroup
	initialized := make(chan struct{})
	var initializedOnce sync.Once
	done := make(chan struct{})
	defer close(done)
	go func() {
		select {
		case <-initialized:
		case <-done:
			return
		}
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				s := current()
				if _, e := os.Stat(filepath.Join(cache, "request-"+hash([]byte(project))+".json")); e == nil && s.State != "setup_failed" && s.State != "explicitly_stopped" {
					launchWorker()
				}
				mu.RLock()
				active := bridge
				mu.RUnlock()
				if active != nil {
					if !apiReady() {
						active.close()
						mu.Lock()
						bridge = nil
						mu.Unlock()
						continue
					}
					select {
					case <-active.done:
						mu.Lock()
						bridge = nil
						mu.Unlock()
						writeState(project, status{State: "api_not_ready", Message: "메모리 연결이 끊겼습니다. MCP를 다시 연결하세요."})
					default:
					}
					continue
				}
				if s.Ready {
					b, e := openBackend()
					if e != nil {
						continue
					}
					result, e := b.call("tools/list", map[string]any{})
					var tools struct {
						Tools []struct {
							Name string `json:"name"`
						} `json:"tools"`
					}
					_ = json.Unmarshal(result, &tools)
					if e != nil || len(tools.Tools) < 2 {
						b.close()
						continue
					}
					mu.Lock()
					bridge = b
					mu.Unlock()
					send(map[string]any{"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
				}
			}
		}
	}()
	defer func() {
		mu.RLock()
		b := bridge
		mu.RUnlock()
		if b != nil {
			b.close()
		}
	}()
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 4096), 4<<20)
	for scanner.Scan() {
		line := append([]byte(nil), scanner.Bytes()...)
		var r rpc
		if json.Unmarshal(line, &r) != nil {
			send(map[string]any{"jsonrpc": "2.0", "id": nil, "error": map[string]any{"code": -32700, "message": "Parse error"}})
			continue
		}
		if len(r.ID) == 0 {
			if r.Method == "notifications/initialized" {
				initializedOnce.Do(func() { close(initialized) })
			}
			if r.Method == "notifications/cancelled" {
				var params struct {
					ID json.RawMessage `json:"requestId"`
				}
				_ = json.Unmarshal(r.Params, &params)
				mu.RLock()
				cancel := pending[string(params.ID)]
				mu.RUnlock()
				if cancel != nil {
					cancel()
				}
			}
			continue
		}
		if r.JSONRPC != "2.0" || r.Method == "" {
			send(map[string]any{"jsonrpc": "2.0", "id": r.ID, "error": map[string]any{"code": -32600, "message": "Invalid request"}})
			continue
		}
		callCtx, cancel := context.WithCancel(ctx)
		mu.Lock()
		pending[string(r.ID)] = cancel
		mu.Unlock()
		requests.Add(1)
		go func(r rpc) {
			defer requests.Done()
			defer cancel()
			defer func() { mu.Lock(); delete(pending, string(r.ID)); mu.Unlock() }()
			var result any
			var err error
			mu.RLock()
			b := bridge
			mu.RUnlock()
			switch r.Method {
			case "initialize":
				var p struct {
					Protocol string `json:"protocolVersion"`
				}
				_ = json.Unmarshal(r.Params, &p)
				if p.Protocol == "" {
					p.Protocol = "2025-11-25"
				}
				result = map[string]any{"protocolVersion": p.Protocol, "capabilities": map[string]any{"tools": map[string]any{"listChanged": true}}, "serverInfo": map[string]any{"name": "agents-memory-local", "version": version}, "instructions": "Local memory installs automatically. Call setup_status while preparing. If configuration is required, use the local browser page; never ask for API keys in chat. " + memoryUseInstructions}
			case "ping":
				result = map[string]any{}
			case "tools/list":
				tools := []any{setupTool()}
				var available []any
				_ = json.Unmarshal(memoryTools, &available)
				if b != nil {
					var v json.RawMessage
					v, err = b.callContext(callCtx, r.Method, map[string]any{})
					if err == nil {
						var t struct {
							Tools []any `json:"tools"`
						}
						err = json.Unmarshal(v, &t)
						available = t.Tools
					}
				}
				tools = append(tools, available...)
				err = nil
				result = map[string]any{"tools": tools}
			case "tools/call":
				var p struct {
					Name string `json:"name"`
				}
				_ = json.Unmarshal(r.Params, &p)
				if p.Name == "setup_status" {
					s := current()
					s.Logs = map[string]string{"setup": filepath.Join(cache, "setup.log"), "operations": filepath.Join(prefix, "integration/logs/operations.log"), "postgres": filepath.Join(prefix, "database/postgres.log"), "service": filepath.Join(prefix, "integration/logs/service.log")}
					s.Scope = map[string]string{"authority": "agents-memory-hindsight-local", "project": project, "runtime_directory": prefix}
					mu.RLock()
					s.Ready = bridge != nil
					mu.RUnlock()
					if s.Ready {
						s.State = "ready"
					}
					message := s.Message
					if s.URL != "" {
						message += "\n" + s.URL
					}
					result = map[string]any{"content": []any{map[string]any{"type": "text", "text": message}}, "structuredContent": s, "isError": false}
				} else if b == nil {
					result = map[string]any{"content": []any{map[string]any{"type": "text", "text": "로컬 메모리를 준비 중입니다. setup_status를 확인하세요."}}, "isError": true}
				} else {
					var params any
					_ = json.Unmarshal(r.Params, &params)
					result, err = b.callContext(callCtx, r.Method, params)
				}
			default:
				send(map[string]any{"jsonrpc": "2.0", "id": r.ID, "error": map[string]any{"code": -32601, "message": "Method not found"}})
				return
			}
			if err != nil {
				result = map[string]any{"content": []any{map[string]any{"type": "text", "text": "로컬 메모리 호출에 실패했습니다. setup_status와 비공개 로그를 확인하세요."}}, "isError": true}
			}
			send(map[string]any{"jsonrpc": "2.0", "id": r.ID, "result": result})
		}(r)
	}
	cancelAll()
	requests.Wait()
	return scanner.Err()
}
func main() {
	syscall.Umask(0077)
	home, _ := os.UserHomeDir()
	home, _ = filepath.EvalSymlinks(home)
	base, _ := os.UserCacheDir()
	flag.StringVar(&prefix, "prefix", filepath.Join(home, ".local/share/agents-memory-hindsight"), "private runtime directory")
	flag.StringVar(&cache, "cache", filepath.Join(base, "agents-memory-setup"), "private setup coordination directory")
	flag.StringVar(&project, "project", "", "current project")
	flag.StringVar(&helper, "helper", "", "verified public setup helper")
	flag.BoolVar(&worker, "worker", false, "background setup worker")
	flag.Parse()
	if !filepath.IsAbs(prefix) || !filepath.IsAbs(cache) || !filepath.IsAbs(helper) {
		fmt.Fprintln(os.Stderr, "agents-memory-local: absolute installation paths are required")
		os.Exit(2)
	}
	if e := privateDir(cache); e != nil {
		fmt.Fprintln(os.Stderr, "agents-memory-local: private setup directory is unavailable")
		os.Exit(2)
	}
	var e error
	if worker {
		e = runWorker()
		if e != nil {
			global(status{State: "setup_failed", Message: e.Error() + " · MCP를 다시 연결하면 재시도합니다."})
		}
	} else {
		project, e = filepath.EvalSymlinks(project)
		if e == nil {
			project, e = filepath.Abs(project)
		}
		if e == nil {
			e = serve()
		}
	}
	if e != nil {
		fmt.Fprintln(os.Stderr, "agents-memory-local:", e)
		os.Exit(2)
	}
}
