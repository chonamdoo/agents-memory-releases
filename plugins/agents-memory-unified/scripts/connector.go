// A setup-status MCP remains connected until the Jev-backed installation is ready.
// Once configured, exec the owned stable launcher. Never read or print keys.
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)

const version = "2.0.0"
const marketplaceVersion = "2.0.3"

type rpc struct {
	ID     json.RawMessage `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

func status() map[string]any {
	base := "bash /path/to/extracted-bundle/install-unified.sh --bundle /path/to/extracted-bundle --reranker-dir /path/to/companion/model --provider jev --client "
	return map[string]any{"ready": false, "server_ready": false, "state": "setup_required", "version": version,
		"marketplace_version": marketplaceVersion, "release_channel": "prerelease",
		"candidate_archive":   "agents-memory-unified-2.0.0-request-scope-v16.tar.gz",
		"candidate_checksums": "JEV197-SHA256SUMS",
		"candidate_url":       "https://github.com/chonamdoo/agents-memory-releases/tree/main/release-candidates/v2.0.0-jev197",
		"model_archive":       "agents-memory-reranker-2.0.0.tar.gz", "model_checksums": "SHA256SUMS",
		"model_url": "https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0",
		"message":   "2.0.0은 시험판입니다. 후보 폴더의 v16 번들을 JEV197-SHA256SUMS로, 릴리즈의 모델 companion을 기존 SHA256SUMS로 각각 검증하세요. 압축을 푼 뒤 현재 앱의 install_commands 명령으로 설치하세요. Claude·OMP 플러그인과 직접 MCP를 중복 등록하지 마세요. Jev 키는 비공개 파일 또는 터미널 숨김 입력을 사용하고 채팅에 보내지 마세요.",
		"install_commands": map[string]string{
			"claude": base + "claude-plugin --project /absolute/project",
			"omp":    base + "omp-plugin --project /absolute/project",
			"codex":  base + "codex --project /absolute/project",
		},
		"guide": "https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md"}
}

func serve(in *os.File, out *os.File) {
	scanner := bufio.NewScanner(in)
	scanner.Buffer(make([]byte, 4096), 2*1024*1024)
	encoder := json.NewEncoder(out)
	for scanner.Scan() {
		var request rpc
		if json.Unmarshal(scanner.Bytes(), &request) != nil {
			continue
		}
		if len(request.ID) == 0 {
			continue
		}
		var result any
		switch request.Method {
		case "initialize":
			var params struct {
				ProtocolVersion string `json:"protocolVersion"`
			}
			_ = json.Unmarshal(request.Params, &params)
			if params.ProtocolVersion == "" {
				params.ProtocolVersion = "2025-11-25"
			}
			result = map[string]any{"protocolVersion": params.ProtocolVersion, "capabilities": map[string]any{"tools": map[string]any{}},
				"serverInfo":   map[string]any{"name": "agents-memory-unified", "version": version},
				"instructions": "Call setup_status. Memory is not ready until the Jev-backed installation is configured; never request keys in chat."}
		case "tools/list":
			result = map[string]any{"tools": []any{map[string]any{"name": "setup_status", "description": "Installation readiness and secure one-time setup instructions.",
				"inputSchema": map[string]any{"type": "object", "properties": map[string]any{}, "additionalProperties": false},
				"annotations": map[string]any{"readOnlyHint": true, "idempotentHint": true}}}}
		case "tools/call":
			var params struct {
				Name string `json:"name"`
			}
			_ = json.Unmarshal(request.Params, &params)
			text, _ := json.Marshal(status())
			result = map[string]any{"content": []any{map[string]any{"type": "text", "text": string(text)}}, "isError": params.Name != "setup_status"}
		case "ping":
			result = map[string]any{}
		default:
			_ = encoder.Encode(map[string]any{"jsonrpc": "2.0", "id": request.ID, "error": map[string]any{"code": -32601, "message": "Method not found"}})
			continue
		}
		_ = encoder.Encode(map[string]any{"jsonrpc": "2.0", "id": request.ID, "result": result})
	}
}

func main() {
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Home directory unavailable")
		os.Exit(2)
	}
	prefix := flag.String("prefix", filepath.Join(home, ".local/share/agents-memory-unified"), "Owned installation")
	project := flag.String("project", "", "Current project")
	flag.Parse()
	if *project == "" {
		*project, _ = os.Getwd()
	}
	launcher := filepath.Join(*prefix, "bin/unified-python")
	connection := filepath.Join(*prefix, "client/local/connection.json")
	if _, err := os.Stat(connection); err == nil {
		if info, err := os.Stat(launcher); err == nil && info.Mode().IsRegular() && info.Mode()&0111 != 0 {
			argv := []string{launcher, "-m", "agents_memory_collab.cli", "mcp", "--connection", connection,
				"--state", filepath.Join(*prefix, "client/local/replica.sqlite"), "--project", filepath.Base(*project)}
			// The SDK validates the private connection and keeps initialization
			// responsive while the launcher's owned service prepares.
			if syscall.Exec(launcher, argv, os.Environ()) == nil {
				return
			}
		}
	}
	serve(os.Stdin, os.Stdout)
}
