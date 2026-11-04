package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fixture(t *testing.T) {
	t.Helper()
	cache = t.TempDir()
	prefix = filepath.Join(cache, "runtime")
	helper = filepath.Join(cache, "helper.py")
	if e := os.Chmod(cache, 0700); e != nil {
		t.Fatal(e)
	}
}
func TestPrivateFilesRejectLinksAndPermissions(t *testing.T) {
	fixture(t)
	p := filepath.Join(cache, "private.json")
	if e := atomic(p, map[string]any{"kept": true}); e != nil {
		t.Fatal(e)
	}
	if _, e := privateRead(p); e != nil {
		t.Fatal(e)
	}
	os.Chmod(p, 0644)
	if _, e := privateRead(p); e == nil {
		t.Fatal("public file accepted")
	}
	os.Chmod(p, 0600)
	os.Link(p, p+".hard")
	if _, e := privateRead(p); e == nil {
		t.Fatal("hard link accepted")
	}
	os.Remove(p + ".hard")
	os.Symlink(p, p+".link")
	if _, e := privateRead(p + ".link"); e == nil {
		t.Fatal("symlink accepted")
	}
}
func TestOneSetupWorkerAndSafeLock(t *testing.T) {
	fixture(t)
	f, e := lock("worker.lock")
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	if other, e := lock("worker.lock"); e == nil {
		other.Close()
		t.Fatal("duplicate setup worker admitted")
	}
}
func TestExistingJevCredentialIsReusedWithoutExposingIt(t *testing.T) {
	fixture(t)
	canary := "SYNTHETIC_KEY_NEVER_IN_STATUS"
	atomic(filepath.Join(prefix, "settings/profile.json"), map[string]any{"provider": "jev", "model": "kept-model"})
	atomic(filepath.Join(prefix, "settings/jev-credential.json"), map[string]any{"schema_version": 1, "api_key": canary})
	r, complete, e := loadRoute()
	if e != nil || !complete || r.Model != "kept-model" || r.Key != "" {
		t.Fatal("saved route changed or key was exposed")
	}
}
func TestBrowserFormIsLocalAndRejectsCrossOriginRequests(t *testing.T) {
	fixture(t)
	result := make(chan route, 1)
	fail := make(chan error, 1)
	go func() {
		r, closePage, e := choose(route{})
		if e != nil {
			fail <- e
			return
		}
		defer closePage()
		result <- r
	}()
	var s status
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if decode(filepath.Join(cache, "worker.json"), &s) == nil && s.URL != "" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if s.URL == "" {
		t.Fatal("settings page did not start")
	}
	u, _ := url.Parse(s.URL)
	if u.Hostname() != "127.0.0.1" {
		t.Fatal("settings page is not loopback")
	}
	resp, e := http.Get(s.URL)
	if e != nil {
		t.Fatal(e)
	}
	html, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(string(html), `type="password"`) || resp.Header.Get("Cache-Control") != "no-store" {
		t.Fatal("unsafe settings form")
	}
	canary := "SYNTHETIC_KEY_NEVER_IN_STATUS"
	body := `{"provider":"jev","key":"` + canary + `"}`
	for _, origin := range []string{"", "https://attacker.invalid"} {
		req, _ := http.NewRequest("POST", s.URL+"configure", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Origin", origin)
		resp, e := http.DefaultClient.Do(req)
		if e != nil {
			t.Fatal(e)
		}
		resp.Body.Close()
		if resp.StatusCode != 403 {
			t.Fatal("cross origin setup accepted")
		}
	}
	req, _ := http.NewRequest("POST", s.URL+"configure", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Origin", u.Scheme+"://"+u.Host)
	resp, e = http.DefaultClient.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	if resp.StatusCode != 202 {
		t.Fatal("valid local setup failed")
	}
	select {
	case r := <-result:
		if r.Key != canary || r.Provider != "jev" {
			t.Fatal("credential input lost")
		}
	case e := <-fail:
		t.Fatal(e)
	case <-time.After(3 * time.Second):
		t.Fatal("form submission stalled")
	}
	state, _ := os.ReadFile(filepath.Join(cache, "worker.json"))
	if strings.Contains(string(state), canary) {
		t.Fatal("key leaked into setup status")
	}
}
func TestDamagedHelperNeverStartsInstallation(t *testing.T) {
	fixture(t)
	os.WriteFile(helper, []byte("tampered"), 0600)
	if e := install(route{Provider: "jev", Key: "synthetic"}); e == nil {
		t.Fatal("tampered helper accepted")
	}
	if _, e := os.Stat(prefix); !os.IsNotExist(e) {
		t.Fatal("installation touched before integrity check")
	}
}
func TestStatusDoesNotContainCallerArguments(t *testing.T) {
	fixture(t)
	project = filepath.Join(cache, "project")
	writeState(project, status{State: "needs_configuration", Message: "Choose a provider"})
	b, e := json.Marshal(current())
	if e != nil || strings.Contains(string(b), "api_key") {
		t.Fatal("unsafe status")
	}
}

func TestStableToolsAreDiscoverableBeforeBackgroundSetupFinishes(t *testing.T) {
 var tools []map[string]any
 if json.Unmarshal(memoryTools,&tools)!=nil||len(tools)!=9 {t.Fatal("invalid stable core tool contract")}
 seen:=map[string]bool{}
 for _,tool:=range tools {
  name,ok:=tool["name"].(string);if !ok||seen[name]{t.Fatal("invalid/duplicate memory tool")};seen[name]=true
  if name=="sync_retain" {schema:=tool["inputSchema"].(map[string]any);props:=schema["properties"].(map[string]any);if _,ok:=props["document_id"];ok{t.Fatal("unsupported document route exposed")}}
 }
}

func TestPreviousVersionFailureDoesNotBlockRepairWorker(t *testing.T) {
	fixture(t)
	project = filepath.Join(cache,"project")
	old := status{Version:"1.0.5",State:"setup_failed",Message:"Old setup failed"}
	if e:=atomic(statePath(project),old);e!=nil {t.Fatal(e)}
	if e:=atomic(filepath.Join(cache,"worker.json"),old);e!=nil {t.Fatal(e)}
	if s:=current();s.State!="pending"||s.Version!=version {t.Fatal("stale failure prevents upgrade retry")}
}
