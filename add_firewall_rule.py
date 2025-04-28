import sys
import xml.etree.ElementTree as ET
import shutil
from datetime import datetime
import subprocess

if len(sys.argv) < 3:
    print("Usage: python3 add_firewall_rule.py <ip> <port> <action>")
    sys.exit(1)

src_ip = sys.argv[1]
st_port = sys.argv[2]
action = sys.argv[3].lower()

CONFIG_PATH = "/conf/config.xml"
BACKUP_PATH = f"/conf/config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
shutil.copy(CONFIG_PATH, BACKUP_PATH)

tree = ET.parse(CONFIG_PATH)
root = tree.getroot()
filter_elem = root.find("filter")
if filter_elem is None:
    filter_elem = ET.SubElement(root, "filter")

 # === 🔍 Check if rule already exists ===
def rule_exists(ip, port, action):
    for rule in filter_elem.findall("rule"):
         try:
            rule_type = rule.find("type").text
            rule_src = rule.find("source/address").text
            rule_dst = rule.find("destination/port").text
            if rule_type == action and rule_src == ip and rule_dst == port:
                 return True
         except:
             continue
    return False

 # === 🧹 Remove rule for "unblock" ===
if action == "unblock":
    removed = False
    for rule in filter_elem.findall("rule"):
         try:
             src = rule.find("source/address").text
             dst = rule.find("destination/port").text
             typ = rule.find("type").text
             if src == src_ip and dst == dst_port and typ == "block":
                 filter_elem.remove(rule)
                 removed = True
         except Exception:
             continue
    result_msg = f"🧹 Removed block rule for {src_ip}:{dst_port}" if removed else "❌ No rule found to remove"

 # === ✅ Add new rule only if not exists ===
else:
     if rule_exists(src_ip, dst_port, action):
         result_msg = f"🔁 Rule already exists: {action} {src_ip}:{dst_port}"
     else:
         rule = ET.SubElement(filter_elem, "rule")
         ET.SubElement(rule, "type").text = "block" if action == "block" else "pass"
         ET.SubElement(rule, "interface").text = "lan"
         ET.SubElement(rule, "ipprotocol").text = "inet"
         ET.SubElement(rule, "protocol").text = "tcp"
         ET.SubElement(rule, "direction").text = "in"
         ET.SubElement(rule, "descr").text = f"{action.upper()} rule from API"
         ET.SubElement(rule, "disabled").text = "0"

         src = ET.SubElement(rule, "source")
         ET.SubElement(src, "address").text = src_ip

         dst = ET.SubElement(rule, "destination")
         ET.SubElement(dst, "port").text = dst_port

         result_msg = f"✅ Rule added: {action} {src_ip}:{dst_port}"

 # === Save and apply ===
tree.write(CONFIG_PATH)
subprocess.run(["configctl", "filter", "reload"])
print(result_msg)
 