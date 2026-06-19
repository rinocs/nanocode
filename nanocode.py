#!/usr/bin/env python3
"""nanocode - minimal coding-agent harness"""

import glob as globlib, json, os, re, subprocess, urllib.request, time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# --- Configuration ---

class Config:
    def __init__(self):
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.openai_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")
        self.model = os.environ.get("MODEL", "")
        self.verbose = os.environ.get("VERBOSE", "0") == "1"
        self.use_memory = os.environ.get("MEMORY", "1") == "1"
        self.use_planner = os.environ.get("PLANNER", "0") == "1"
        self.use_reviewer = os.environ.get("REVIEWER", "0") == "1"

        if not self.model:
            if self.openai_key: self.model = "gpt-4o"
            elif self.openrouter_key: self.model = "anthropic/claude-3-5-sonnet"
            else: self.model = "claude-3-5-sonnet-20241022"

        if self.openai_key: self.api_url = self.openai_base
        elif self.openrouter_key: self.api_url = "https://openrouter.ai/api/v1/messages"
        else: self.api_url = "https://api.anthropic.com/v1/messages"

        self.provider = "openai" if self.openai_key else "anthropic"

cfg = Config()

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = "\033[34m", "\033[36m", "\033[32m", "\033[33m", "\033[31m"

# --- Memory System ---

class Memory:
    def __init__(self, path=".nanocode_memory.json"):
        self.path = path
        self.data = {"scratchpad": "", "history": [], "summary": ""}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.data.update(json.load(f))
            except: pass

    def save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except: pass

    def add_history(self, role, content):
        self.data["history"].append({"role": role, "content": content})
        if len(self.data["history"]) > 20:
            self.data["history"] = self.data["history"][-20:]
        self.save()

    def get_context(self):
        ctx = []
        if self.data["summary"]: ctx.append(f"Recent summary: {self.data['summary']}")
        if self.data["scratchpad"]: ctx.append(f"Scratchpad: {self.data['scratchpad']}")
        return "\n".join(ctx)

memory = Memory() if cfg.use_memory else None

# --- Tool implementations ---

def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))

def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"

def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text: return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"

def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(files, key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0, reverse=True)
    return "\n".join(files) or "none"

def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            if os.path.isdir(filepath): continue
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except: pass
    return "\n".join(hits[:50]) or "none"

def bash(args):
    proc = subprocess.Popen(args["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if line:
                if cfg.verbose: print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"

TOOLS = {
    "read": ("Read file with line numbers", {"path": "string", "offset": "number?", "limit": "number?"}, read),
    "write": ("Write content to file", {"path": "string", "content": "string"}, write),
    "edit": ("Replace old with new in file", {"path": "string", "old": "string", "new": "string", "all": "boolean?"}, edit),
    "glob": ("Find files by pattern", {"pat": "string", "path": "string?"}, glob),
    "grep": ("Search files for regex", {"pat": "string", "path": "string?"}, grep),
    "bash": ("Run shell command", {"cmd": "string"}, bash),
}

# --- Runtime & Orchestration ---

class Session:
    def __init__(self, system_prompt: str):
        self.messages = []
        self.system_prompt = system_prompt
        if memory:
            self.system_prompt += f"\n\nMemory Context:\n{memory.get_context()}"

    def add_message(self, role: str, content: Any):
        self.messages.append({"role": role, "content": content})
        if memory and role == "user" and isinstance(content, str):
            memory.add_history(role, content)

    def call_api(self, tools_override=None):
        if cfg.provider == "openai":
            return self._call_openai(tools_override)
        return self._call_anthropic(tools_override)

    def _call_anthropic(self, tools_override):
        tools = tools_override if tools_override is not None else self.make_schema()
        payload = {"model": cfg.model, "max_tokens": 8192, "system": self.system_prompt, "messages": self.messages}
        if tools: payload["tools"] = tools

        headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        if cfg.openrouter_key: headers["Authorization"] = f"Bearer {cfg.openrouter_key}"
        else: headers["x-api-key"] = cfg.anthropic_key

        return self._request(cfg.api_url, payload, headers)

    def _call_openai(self, tools_override):
        messages = [{"role": "system", "content": self.system_prompt}]
        for m in self.messages:
            role, content = m["role"], m["content"]
            if role == "user" and isinstance(content, list):
                for block in content:
                    if block["type"] == "tool_result":
                        messages.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]})
            elif role == "assistant" and isinstance(content, list):
                text = ""
                tool_calls = []
                for block in content:
                    if block["type"] == "text": text += block["text"]
                    if block["type"] == "tool_use":
                        tool_calls.append({"id": block["id"], "type": "function", "function": {"name": block["name"], "arguments": json.dumps(block["input"])}})
                msg = {"role": "assistant", "content": text or None}
                if tool_calls: msg["tool_calls"] = tool_calls
                messages.append(msg)
            else:
                messages.append({"role": role, "content": content})

        tools = []
        for name, (desc, params, _) in TOOLS.items():
            props = {}
            required = []
            for p_name, p_type in params.items():
                opt = p_type.endswith("?")
                base = p_type.rstrip("?")
                props[p_name] = {"type": "integer" if base == "number" else "boolean" if base == "boolean" else base}
                if not opt: required.append(p_name)
            tools.append({"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": required}}})

        payload = {"model": cfg.model, "messages": messages}
        if tools and tools_override is None: payload["tools"] = tools

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cfg.openai_key}"}
        res = self._request(cfg.api_url, payload, headers)

        choice = res["choices"][0]["message"]
        content = []
        if choice.get("content"):
            content.append({"type": "text", "text": choice["content"]})
        if choice.get("tool_calls"):
            for tc in choice["tool_calls"]:
                content.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": json.loads(tc["function"]["arguments"])})
        return {"content": content}

    def _request(self, url, payload, headers):
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
                with urllib.request.urlopen(req) as res:
                    return json.loads(res.read())
            except Exception as e:
                if attempt == 2: raise e
                time.sleep(2 ** attempt)

    def make_schema(self):
        result = []
        for name, (desc, params, _) in TOOLS.items():
            props = {}
            req = []
            for p_name, p_type in params.items():
                opt = p_type.endswith("?")
                base = p_type.rstrip("?")
                props[p_name] = {"type": "integer" if base == "number" else "boolean" if base == "boolean" else base}
                if not opt: req.append(p_name)
            result.append({"name": name, "description": desc, "input_schema": {"type": "object", "properties": props, "required": req}})
        return result

def run_agent(user_input: str):
    session = Session(f"Concise coding assistant. cwd: {os.getcwd()}")

    if cfg.use_planner:
        print(f"{YELLOW}⏺ Planning...{RESET}")
        plan_session = Session("You are a planner. Break the user request into a short bulleted plan.")
        plan_session.add_message("user", user_input)
        res = plan_session.call_api(tools_override=[])
        plan_text = res["content"][0]["text"]
        print(f"  {DIM}{plan_text[:100]}...{RESET}")
        session.system_prompt += f"\n\nPlanned steps:\n{plan_text}"

    session.add_message("user", user_input)

    while True:
        response = session.call_api()
        content = response.get("content", [])
        tool_results = []

        for block in content:
            if block["type"] == "text":
                print(f"\n{CYAN}⏺{RESET} {re.sub(r'\*\*(.+?)\*\*', f'{BOLD}\\1{RESET}', block['text'])}")
            if block["type"] == "tool_use":
                name, args, tid = block["name"], block["input"], block["id"]
                preview = str(list(args.values())[0])[:50] if args else ""
                print(f"\n{GREEN}⏺ {name.capitalize()}{RESET}({DIM}{preview}{RESET})")
                try:
                    res = TOOLS[name][2](args)
                except Exception as e:
                    res = f"error: {e}"

                res_lines = res.split("\n")
                preview = res_lines[0][:60] + ("..." if len(res_lines) > 1 or len(res_lines[0]) > 60 else "")
                print(f"  {DIM}⎿  {preview}{RESET}")
                tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": res})

        session.add_message("assistant", content)
        if not tool_results: break
        session.add_message("user", tool_results)

    if cfg.use_reviewer:
        print(f"\n{YELLOW}⏺ Reviewing...{RESET}")
        rev_session = Session("You are a reviewer. Check if the task was completed correctly. Respond with 'OK' or suggestions.")
        rev_session.add_message("user", f"Original Task: {user_input}\n\nAgent History: {json.dumps(session.messages[-4:])}")
        res = rev_session.call_api(tools_override=[])
        rev_text = res["content"][0]["text"]
        if "OK" not in rev_text.upper():
            print(f"{YELLOW}⏺ Review Suggestion:{RESET} {rev_text}")

# --- CLI ---

def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{cfg.model} ({cfg.provider}) | {os.getcwd()}{RESET}")
    if cfg.use_memory: print(f"{DIM}Memory enabled ({memory.path}){RESET}")

    while True:
        try:
            print(f"{DIM}{'─' * 40}{RESET}")
            cmd = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            if not cmd: continue
            if cmd in ("/q", "exit"): break
            if cmd == "/c":
                if memory: memory.data["history"] = []; memory.save()
                print(f"{GREEN}⏺ Cleared{RESET}")
                continue
            run_agent(cmd)
        except (KeyboardInterrupt, EOFError): break
        except Exception as e: print(f"{RED}⏺ Error: {e}{RESET}")

if __name__ == "__main__":
    main()
