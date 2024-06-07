from xml.etree import ElementTree as ET

from tinydb import table

from bp_class import Pod


def generate_opml(pod_tbl: table.Table, filename) -> str:
    """Builds an OPML (Outline Processor Markup Language) document from a list of feeds."""

    root = ET.Element("opml", {"version": "1.0"})
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = "Bilipod feeds"
    body = ET.SubElement(root, "body")

    for pod_info in pod_tbl.all():
        pod = Pod.from_dict(pod_info)
        if not pod.opml:
            continue

        title = f"{pod.title}[{pod.keyword}]" if pod.keyword else pod.title
        ET.SubElement(
            body,
            "outline",
            {
                "text": pod.description,
                "type": "rss",
                "xmlUrl": pod.xml_url,
                "title": title,
            },
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t", level=0)
    tree.write(filename, encoding="utf-8", xml_declaration=False)
