// A setup-status MCP remains connected before the user selects a provider.
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

const version = "1.0.8"
const install = "https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/server/install-unified.sh"

type rpc struct {
	ID     json.RawMessage `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

func status() map[string]any {
	return map[string]any{"ready": false, "server_ready": false, "state": "setup_required", "version": version,
		"message":     "설치 위치와 Claude CLI·Codex CLI·Jev 중 하나를 한 번 선택하세요. Jev 키는 터미널에서 숨김 입력하며 채팅에 보내지 마세요.",
		"install_url": install, "guide": "https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.8/distribution/server/README.ko.md"}
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
				"instructions": "Call setup_status. Memory is not ready until the selected provider and installation are configured; never request keys in chat."}
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
