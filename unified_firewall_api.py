#!/usr/bin/env python3
"""
unified_firewall_api.py

Flask API to handle both voice (vc2.py) and mobile app requests for OPNsense firewall.
Supports natural‐language commands via Gemma and direct JSON commands from the app.
"""
import os
import re
import json
import ast
import traceback
from flask import Flask, request, jsonify
import requests
import paramiko
from paramiko.ssh_exception import NoValidConnectionsError
from dotenv import load_dotenv

# ─── Load configuration from .env ─────────────────────────────────────────
load_dotenv()
API_KEY        = os.getenv("API_KEY",            "fyp_super_secure_2025_key")
FIREWALL_HOST  = os.getenv("FIREWALL_HOST",      "192.168.1.101")
FIREWALL_USER  = os.getenv("FIREWALL_USER",      "root")
FIREWALL_PASS  = os.getenv("FIREWALL_PASS",      "opnsense")
ADD_SCRIPT     = os.getenv("RULE_SCRIPT",        "/root/add_firewall_rule.py")
LIST_SCRIPT    = os.getenv("LIST_SCRIPT",        "/root/list_firewall_rules.py")
GEMMA_MODEL    = os.getenv("GEMMA_MODEL",        "gemma3:12b")
GEMMA_API_URL  = os.getenv("GEMMA_API_URL",      "http://localhost:11434/api/generate")

app = Flask(__name__)

# ─── Global exception handler ─────────────────────────────────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    app.logger.error(tb)
    return jsonify({
        "error":     str(e),
        "exception": e.__class__.__name__,
        "traceback": tb.splitlines()[-5:]
    }), 500

# ─── Helpers ───────────────────────────────────────────────────────────────
def authorized(req):
    return req.headers.get("x-api-key", "") == API_KEY

def ssh_cmd(cmd: str) -> str:
    """
    Execute `cmd` on the firewall via SSH (Paramiko).
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            FIREWALL_HOST,
            username=FIREWALL_USER,
            password=FIREWALL_PASS,
            port=22,
            timeout=10
        )
    except NoValidConnectionsError as e:
        raise RuntimeError(f"SSH connection failed: {e}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.close()
    if exit_status != 0:
        raise RuntimeError(err or out or f"SSH exit status {exit_status}")
    return out

def call_gemma(nl: str) -> dict:
    """
    Send natural‐language `nl` to Gemma and parse the JSON reply.
    """
    payload = {
        "model":  GEMMA_MODEL,
        "system": (
            "You are a network firewall assistant. "
            "if valid port range(0 to 65535) then continue else throw ERROR"
            "Convert the user's instruction into exactly one JSON object "
            "with keys: [action, ip, port]. "
            "action must be one of: block, allow, remove, unblock, list. "
            "ip must be an IPv4 string or empty. "
            "port must be a TCP port string or 'all'. "
            "Respond with pure JSON and no extra text."
            "check for valid port range if not then throw Error: invalid-port"
        ),
        "prompt": nl,
        "stream": False
    }
    r = requests.post(GEMMA_API_URL, json=payload, timeout=20)
    r.raise_for_status()
    raw = r.json().get("response", "").strip()
    # strip Markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as ex:
        raise RuntimeError(f"Gemma JSON parse failed: {ex}")
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Gemma returned non-dict JSON: {parsed}")
    return parsed

def load_rules() -> list:
    """
    Run list_firewall_rules.py and return a list of rule‐dicts.
    """
    out = ssh_cmd(f"python3 {LIST_SCRIPT}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return ast.literal_eval(out)

def process_command(cmd: dict) -> dict:
    """
    Apply a parsed command dict with keys action, ip, port.
    Returns a result dict for JSON response.
    """
    action = cmd.get("action","").lower()
    ip     = cmd.get("ip","")
    port   = str(cmd.get("port","all"))

    # LIST
    if action == "list":
        rules = load_rules()
        if ip:
            rules = [r for r in rules if r.get("ip")==ip]
        return {"status":"ok","rules":rules}

    # UNBLOCK/REMOVE_ALL
    if action in ("remove","unblock") and port=="all":
        if not ip:
            raise ValueError("Missing IP for unblock all")
        rules = load_rules()
        deleted = []
        for r in rules:
            if r.get("ip")==ip:
                p = r.get("port")
                ssh_cmd(f"python3 {ADD_SCRIPT} {ip} {p} unblock")
                deleted.append({"ip":ip,"port":p})
        return {"status":"unblocked_all","deleted":deleted}

    # SINGLE BLOCK/ALLOW/REMOVE
    if action not in ("block","allow","remove","unblock"):
        raise ValueError(f"Unsupported action: {action}")
    if not ip or not port:
        raise ValueError(f"Missing ip or port: {cmd}")

    # map to script action
    if action == "allow":
        script_action = "pass"
    elif action == "remove":
        script_action = "unblock"
    else:
        script_action = action

    result = ssh_cmd(f"python3 {ADD_SCRIPT} {ip} {port} {script_action}")
    return {"status":"ok","result":result}

# ─── API Endpoints ───────────────────────────────────────────────────────
@app.route("/api/voice", methods=["POST"])
def voice_api():
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    text = data.get("text","").strip()
    if not text:
        return jsonify({"error":"No text provided"}), 400
    cmd = call_gemma(text)
    res = process_command(cmd)
    return jsonify(res)

@app.route("/api/rule", methods=["POST"])
def rule_api():
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    # expect direct JSON with keys action, ip, port
    cmd = {
        "action": data.get("action",""),
        "ip":     data.get("ip",""),
        "port":   data.get("port","all")
    }
    res = process_command(cmd)
    return jsonify(res)

@app.route("/api/rules", methods=["GET"])
def rules_api():
    if not authorized(request):
        return jsonify({"error":"Unauthorized"}), 401
    ipf = request.args.get("ip","").strip() or None
    rules = load_rules()
    if ipf:
        rules = [r for r in rules if r.get("ip")==ipf]
    return jsonify(rules)

# ─── Entry Point ────────────────────────────────────────────────────────
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
