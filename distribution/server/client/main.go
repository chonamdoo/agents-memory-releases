// Cross-platform stdio transport for the optional remote collaboration server.
// Credentials stay in the selected environment variable, never in arguments.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

func run(input io.Reader, output io.Writer, endpoint, token string) error {
	parsed, err := url.Parse(endpoint)
	if err != nil || parsed.Host == "" || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" || (parsed.Path != "" && parsed.Path != "/") {
		return fmt.Errorf("choose a server origin without a path or credentials")
	}
	local := parsed.Hostname() == "127.0.0.1" || parsed.Hostname() == "localhost" || parsed.Hostname() == "::1"
	if parsed.Scheme != "https" && !(parsed.Scheme == "http" && local) {
		return fmt.Errorf("HTTPS is required except for loopback testing")
	}
	if !strings.HasPrefix(token, "amc_") || len(token) > 100 || strings.ContainsAny(token, " \r\n\t") {
		return fmt.Errorf("set the selected token environment variable")
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	client := &http.Client{Timeout: 60 * time.Second, Transport: transport,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	defer transport.CloseIdleConnections()
	scanner := bufio.NewScanner(input)
	scanner.Buffer(make([]byte, 4096), 1048576)
	version := "2026-07-28"
	capabilities := map[string]any{}
	encoder := json.NewEncoder(output)
	for scanner.Scan() {
		body := append([]byte(nil), scanner.Bytes()...)
		var request struct {
			ID     json.RawMessage `json:"id"`
			Method string          `json:"method"`
			Params struct {
				Name string `json:"name"`
			} `json:"params"`
		}
		if json.Unmarshal(body, &request) != nil {
			return fmt.Errorf("invalid JSON-RPC input")
		}
		// MCP 2 HTTP envelopes carry transport metadata which stdio clients omit.
		var envelope map[string]any
		if json.Unmarshal(body, &envelope) != nil {
			return fmt.Errorf("invalid JSON-RPC input")
		}
		params, ok := envelope["params"].(map[string]any)
		if !ok {
			params = map[string]any{}
			envelope["params"] = params
		}
		if request.Method == "initialize" {
			if v, ok := params["protocolVersion"].(string); ok {
				version = v
			}
			if v, ok := params["capabilities"].(map[string]any); ok {
				capabilities = v
			}
		}
		meta, ok := params["_meta"].(map[string]any)
		if !ok {
			meta = map[string]any{}
			params["_meta"] = meta
		}
		meta["io.modelcontextprotocol/protocolVersion"] = version
		meta["io.modelcontextprotocol/clientCapabilities"] = capabilities
		body, err = json.Marshal(envelope)
		if err != nil {
			return fmt.Errorf("invalid JSON-RPC input")
		}
		r, err := http.NewRequest("POST", strings.TrimRight(endpoint, "/")+"/mcp", bytes.NewReader(body))
		if err != nil {
			return fmt.Errorf("invalid endpoint")
		}
		r.Header.Set("Authorization", "Bearer "+token)
		r.Header.Set("Content-Type", "application/json")
		r.Header.Set("Accept", "application/json, text/event-stream")
		r.Header.Set("MCP-Protocol-Version", version)
		r.Header.Set("MCP-Method", request.Method)
		if request.Params.Name != "" {
			r.Header.Set("MCP-Name", request.Params.Name)
		}
		response, callErr := client.Do(r)
		var raw []byte
		statusCode := 0
		if callErr == nil {
			statusCode = response.StatusCode
			raw, callErr = io.ReadAll(io.LimitReader(response.Body, 4194305))
			response.Body.Close()
			if response.StatusCode < 200 || response.StatusCode >= 300 || len(raw) > 4194304 {
				callErr = fmt.Errorf("remote request refused")
			}
		}
		if len(request.ID) == 0 {
			continue
		}
		if callErr != nil || !json.Valid(raw) {
			if err := encoder.Encode(map[string]any{"jsonrpc": "2.0", "id": request.ID,
				"error": map[string]any{"code": -32000, "message": fmt.Sprintf("Memory server unavailable or access refused (HTTP %d); check server/token settings", statusCode)}}); err != nil {
				return err
			}
			continue
		}
		var result struct {
			Result struct {
				ProtocolVersion string `json:"protocolVersion"`
			} `json:"result"`
		}
		if request.Method == "initialize" && json.Unmarshal(raw, &result) == nil && result.Result.ProtocolVersion != "" {
			version = result.Result.ProtocolVersion
		}
		if _, err := fmt.Fprintln(output, string(raw)); err != nil {
			return err
		}
	}
	return scanner.Err()
}

func main() {
	endpoint := flag.String("url", "", "HTTPS collaboration server origin")
	variable := flag.String("token-env", "AM_COLLAB_TOKEN", "credential environment variable name")
	flag.Parse()
	if err := run(os.Stdin, os.Stdout, *endpoint, os.Getenv(*variable)); err != nil {
		fmt.Fprintln(os.Stderr, "agents-memory-cloud: "+err.Error())
		os.Exit(1)
	}
}
