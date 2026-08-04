"""End-to-end exercise of all five MCP tools over real stdio JSON-RPC.

Spawns ``mcp_server.py`` exactly the way an MCP client (Claude Desktop, etc.)
does — a subprocess speaking JSON-RPC over stdin/stdout — then calls every
tool with realistic inputs and checks the answers. No pytest, no mocks, no
imports from the package: if this passes, a real client will work.

Run from the repository root:

    python demo/mcp_e2e.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / "demo" / "test_receipt.txt"

passed: list[str] = []
failed: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (passed if ok else failed).append(label)
    print(f"  [{'OK' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


class Server:
    """Minimal JSON-RPC-over-stdio client for one server process."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "mcp_server.py")],
            cwd=ROOT,  # the receipt sandbox roots itself here
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        self._id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(
                    "server exited early - run `python mcp_server.py` to see its startup error"
                )
            msg = json.loads(line)
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method} failed: {msg['error']}")
                return msg["result"]

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def call_tool(self, name: str, arguments: dict) -> dict:
        """tools/call, with the JSON payload inside the text content parsed."""
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        text = result["content"][0]["text"]
        if result.get("isError"):
            raise RuntimeError(f"{name} returned an error: {text}")
        return json.loads(text)

    def _send(self, obj: dict) -> None:
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def main() -> int:
    print(f"repo: {ROOT}")
    server = Server()
    try:
        info = server.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-e2e", "version": "1.0"},
            },
        )
        server.notify("notifications/initialized")
        print(f"connected: {info['serverInfo']['name']} {info['serverInfo'].get('version', '')}\n")

        print("tools/list")
        tools = sorted(t["name"] for t in server.request("tools/list")["tools"])
        expected = [
            "category_classifier",
            "duplicate_detector",
            "policy_checker",
            "receipt_parser",
            "report_summariser",
        ]
        check("exactly the five public tools", tools == expected, ", ".join(tools))

        print("\n1. policy_checker - $187 dinner against the $75 meals cap")
        r = server.call_tool(
            "policy_checker",
            {
                "employee_id": "emp-001",
                "amount": "187.00",
                "merchant": "The Chophouse",
                "expense_date": "2026-07-26",
                "category": "Meals & Entertainment",
                "description": "Client dinner",
                "has_receipt": True,
            },
        )
        codes = [v["code"] for v in r["violations"]]
        check("status is fail", r["status"] == "fail", r["status"])
        check("flags OVER_CATEGORY_LIMIT", "OVER_CATEGORY_LIMIT" in codes, ", ".join(codes))

        print("\n2. receipt_parser - sandboxed file read of demo/test_receipt.txt")
        r = server.call_tool("receipt_parser", {"file_path": str(RECEIPT)})
        check("merchant extracted", r["merchant"] == "GRAND HORIZON HOTEL", r["merchant"])
        check("total is 523.83", r["total"] == "523.83", r["total"])
        check("arithmetic reconciles", r["reconciles"] is True, f"delta={r['delta']}")
        check("four line items", len(r["line_items"]) == 4)

        print("\n3. category_classifier - 'Airport transfer' / Uber")
        r = server.call_tool(
            "category_classifier", {"description": "Airport transfer", "merchant": "Uber"}
        )
        check("classified as Travel - Ground", r["category"] == "Travel - Ground", r["category"])
        check("confident", r["confidence"] >= 0.9, str(r["confidence"]))

        print("\n4. duplicate_detector - the seeded resubmitted Uber ride")
        r = server.call_tool(
            "duplicate_detector",
            {
                "employee_id": "emp-002",
                "total": "42.50",
                "receipt_datetime": "2026-06-05T07:30:00",
            },
        )
        reasons = [m["reason"] for m in r["matches"]]
        check(
            "finds the stored duplicates", len(r["matches"]) >= 1, f"{len(r['matches'])} match(es)"
        )
        check("as an exact match", "EXACT_KEY" in reasons, ", ".join(reasons) or "none")
        check("risk is high", r["risk"] in ("high", "HIGH"), str(r["risk"]))

        print("\n5. report_summariser - aggregate the stored demo data, no input")
        r = server.call_tool("report_summariser", {})
        blob = json.dumps(r)
        check("summarises the six seeded items", '"1015.88"' in blob or "1015.88" in blob)
        check("produces a narrative", bool(r.get("narrative") or r.get("summary")))
    finally:
        server.close()

    print(
        f"\n{'ALL GOOD' if not failed else 'PROBLEMS'}: {len(passed)} passed, {len(failed)} failed"
    )
    if failed:
        for label in failed:
            print(f"  - {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
