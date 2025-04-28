import xml.etree.ElementTree as ET
CONFIG_PATH = "/conf/config.xml"
tree = ET.parse(CONFIG_PATH)
root = tree.getroot()

filter_elem = root.find("filter")
rules = []

if filter_elem is not None:
    for rule in filter_elem.findall("rule"):
        try:
             rule_type = rule.find("type").text
             interface = rule.find("interface").text
             src = rule.find("source/address").text
             dst = rule.find("destination/port").text
             rules.append({
                "type": rule_type,
                "ip": src,
                "port": dst,
                "interface": interface
           })
        except:
             continue
print(rules)