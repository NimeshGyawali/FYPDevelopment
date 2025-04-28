#!/usr/bin/env python3
"""
Flask bridge – speech‐to‐OPNsense via SSH (Paramiko).
"""
import os
import json
import logging
import re
from typing import Dict, Any, Tuple

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests
import paramiko
from urllib3.exceptions import InsecureRequestWarning

# ─── Bootstrap & config ───────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")

# disable warnings for self‐signed certs (if you ever use REST)
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# local API key for mobile/voice client
API_KEY           = os.getenv("API_KEY", "")
# OPNsense SSH credentials
OPN_SSH_HOST      = os.getenv("OPNSENSE_HOST", "192.168.1.101")
OPN_SSH_PORT      = int(os.getenv("OPNSENSE_SSH_PORT", "22"))
OPN_SSH_USER      = os.getenv("OPNSENSE_SSH_USER", "root")
OPN_SSH_PASS      = os.getenv("OPNSENSE_SSH_PASS", "opnsense")

# Gemma / Ollama
GEMMA_MODEL       = os.getenv("GEMMA_MODEL", "gemma3:12b")
GEMMA_API_URL     = os.getenv("GEMMA_API_URL", "http://127.0.0.1:11434/api/generate")

app = Flask(__name__)

# ─── SSH helper ─────────────────────────────────────────────
def _ssh_cmd(cmd: str, timeout: float = 10.0) -> str:
    """
    Execute `cmd` over SSH on the OPNsense box, return stdout.
    """
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=OPN_SSH_HOST,
            port=OPN_SSH_PORT,
            username=OPN_SSH_USER,
            password=OPN_SSH_PASS,
            timeout=timeout
        )
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="ignore").strip()
        err = stderr.read().decode("utf-8", errors="ignore").strip()
        client.close()
        if err:
            logging.warning("SSH stderr: %s", err)
        return out
    except Exception as e:
        raise RuntimeError(f"SSH error: {e}") from e

# ─── Text→JSON via LLM ──────────────────────────────────────
def _gemma(prompt: str) -> Dict[str, Any]:
    payload = {
        "model":  GEMMA_MODEL,
        "system": (
            "You are a network assistant. Return *only* a single JSON object "
            "representing a firewall command with keys [command, ip, port, action]."
        ),
        "prompt": prompt,
        "stream": False,
    }
    resp = requests.post(GEMMA_API_URL, json=payload, timeout=60)
    resp.raise_for_status()
    raw = resp.json().get("response", "").strip()
    logging.info("Gemma raw >>> %s", raw.replace("\n","\\n")[:200])

    # strip markdown fences if any
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw).rstrip("`").rstrip()
    # pull out the first JSON object
    try:
        start = raw.index("{")
        end   = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception as e:
        raise ValueError("Gemma JSON parse failed") from e

# ─── High-level rule mapper ─────────────────────────────────
def _apply_rule(cmd: Dict[str, Any]) -> Dict[str, Any]:
    c    = cmd.get("command","").lower()
    ip   = cmd.get("ip","")
    port = cmd.get("port","")
    # unblock-all: special handling
    if c=="unblock" and port.lower()=="all":
        # list existing rules via SSH script
        out = _ssh_cmd(f"python3 /root/list_firewall_rules.py")
        deleted = []
        for line in out.splitlines():
            if ip in line:
                p = line.strip().split()[-1]
                _ssh_cmd(f"python3 /root/add_firewall_rule.py {ip} {p} unblock")
                deleted.append({"ip":ip,"port":p})
        return {"status":"unblocked_all","rules":deleted}

    # single block/unblock
    if c in ("block","unblock"):
        result = _ssh_cmd(
            f"python3 /root/add_firewall_rule.py {ip} {port} {c}"
        )
        return {"status":"ok","result": result}

    if c=="list":
        out = _ssh_cmd(f"python3 /root/list_firewall_rules.py")
        return {"status":"ok","rules": out}

    return {"error":"Unknown command"}

# ─── Endpoints ──────────────────────────────────────────────
@app.route("/api/voice", methods=["POST"])
def voice() -> Tuple[Any,int]:
    if request.headers.get("x-api-key","") != API_KEY:
        return jsonify({"error":"unauthorized"}), 401

    text = (request.json or {}).get("text","").strip()
    logging.info("NL request: %s", text)
    if not text:
        return jsonify({"error":"no text"}), 400

    try:
        cmd = _gemma(text)
    except Exception:
        logging.exception("Gemma failed")
        return jsonify({"error":"llm"}), 500

    try:
        res = _apply_rule(cmd)
        return jsonify({"ok":res})
    except Exception:
        logging.exception("Firewall op failed")
        return jsonify({"error":"firewall"}), 500

@app.route("/api/rules", methods=["GET"])
def list_rules():
    if request.headers.get("x-api-key","") != API_KEY:
        return jsonify({"error":"unauthorized"}), 401
    try:
        out = _ssh_cmd("python3 /root/list_firewall_rules.py")
        return jsonify({"status":"ok","rules": out})
    except Exception:
        logging.exception("rule list failed")
        return jsonify({"error":"firewall"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
