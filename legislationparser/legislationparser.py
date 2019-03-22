import lxml.etree as ET
import re
from yattag import Doc


def un_namespace(html):
    return re.sub(r"<(/?)[a-z]+:", r"<\1", html)


def slugify(txt):
    return re.sub(r"[^\w]+", "-", txt.lower())


class LegislationParser(object):
    ns = {
        "l": "http://www.legislation.gov.uk/namespaces/legislation",
        "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
        "dc": "http://purl.org/dc/elements/1.1/",
        "html": "http://www.w3.org/1999/xhtml",
        "m": "http://www.w3.org/1998/Math/MathML",
    }

    def __init__(self, data):
        self.xml = ET.fromstring(data)
        self.type = None
        self._part_tags = [
            self.ns_tag(tag) for tag in
            [
                "Pblock",
                "PsubBlock",
                "Part",
                "Chapter",
                "ScheduleBody",
            ]
        ]

    def get_body(self):
        """ Get the body of the legislation as a HTML5 snippet """
        self.doc, self.tag, self.text = Doc().tagtext()

        root = self.get_root()
        if root is None:
            return None
        body = root.find("./l:Body", namespaces=self.ns)

        self.parse_parts(body)
        return self.doc.getvalue()

    def get_schedules(self):
        self.doc, self.tag, self.text = Doc().tagtext()
        root = self.get_root()
        if root is None:
            return None
        schedules = root.find("./l:Schedules", namespaces=self.ns)
        if schedules is not None:
            self.parse_schedule_parts(schedules)
        return self.doc.getvalue()

    def get_root(self):
        """ Get the root element of the legislation """
        if self.xml.find("./l:Primary", namespaces=self.ns) is not None:
            self.type = "primary"
            return self.xml.find("./l:Primary", namespaces=self.ns)
        elif self.xml.find("./l:Secondary", namespaces=self.ns) is not None:
            self.type = "secondary"
            return self.xml.find("./l:Secondary", namespaces=self.ns)
        else:
            # In some cases the instrument is only available as PDF.
            return None

    def get_preamble(self):
        root = self.get_root()
        if root is None:
            return None
        if self.type == "primary":
            prelims = root.find("./l:PrimaryPrelims", namespaces=self.ns)
        elif self.type == "secondary":
            prelims = root.find("./l:SecondaryPrelims", namespaces=self.ns)

        return {
            "title": prelims.xpath("string(./l:Title)", namespaces=self.ns),
            "number": prelims.xpath("string(./l:Number)", namespaces=self.ns),
            "long_title": prelims.xpath("string(./l:LongTitle)", namespaces=self.ns),
            "enacting_text": prelims.xpath(
                "string(./l:PrimaryPreamble/l:EnactingText)", namespaces=self.ns
            ),
        }

    def get_metadata(self):
        md = self.xml.find("./ukm:Metadata", namespaces=self.ns)
        keys = {
            "title": "dc:title",
            "description": "dc:description",
            "modified": "dc:modified",
        }
        data = {}
        for key, selector in keys.items():
            el = md.find(selector, namespaces=self.ns)
            if el is not None:
                data[key] = el.text

        return data

    def parse_schedule_parts(self, schedules):
        for schedule in schedules.xpath("./l:Schedule", namespaces=self.ns):
            with self.tag("section", klass="schedule"):
                self.get_title(schedule, 2)
                self.parse_parts(schedule)

    def parse_parts(self, body, level=2):
        for part in body.xpath("./*", namespaces=self.ns):
            if part.tag in self._part_tags:
                attrs = []
                if part.get("id"):
                    attrs = [("id", part.get("id"))]
                with self.tag("section", *attrs):
                    # Title here is (usually) duplicated
                    # self.get_title(part, level)
                    if part.find("./l:P1", namespaces=self.ns) or part.find(
                        "./l:Tabular", namespaces=self.ns
                    ) or part.find("./l:BlockAmendment", namespaces=self.ns):
                        # In some cases a Pblock contains bare elements, special-case that here.
                        self.parse_section_items(part, 0)
                    else:
                        self.parse_parts(part, level=level + 1)
            elif part.tag == self.ns_tag("P1group"):
                id_slug = slugify(part.xpath("string(./l:Title)", namespaces=self.ns))
                with self.tag("section", id=id_slug):
                    self.get_title(part, 3)
                    self.parse_section(part.findall("./l:P1", namespaces=self.ns), 1)
            elif part.tag in (self.ns_tag("Title"), self.ns_tag("TitleBlock")):
                self.get_title(body, 2)
            elif part.tag == self.ns_tag("Number"):
                # TODO: render these
                continue
            elif part.tag == self.ns_tag("SignedSection"):
                # TODO: render
                continue
            elif part.tag == self.ns_tag("Text"):
                with self.tag("p"):
                    self.get_text(part)
            elif part.tag == self.ns_tag("Reference"):
                continue
            else:
                raise Exception("Unknown part tag: ", ET.tostring(part))

    def ns_tag(self, name):
        return "{" + self.ns["l"] + "}" + name

    def clean_text(self, txt):
        if txt is None:
            return ""
        return re.sub(r"\s+", " ", txt)

    def get_title(self, el, level):
        part = el.xpath("string(./l:Number)", namespaces=self.ns)
        title = el.xpath("string(./l:Title|./l:TitleBlock/l:Title)", namespaces=self.ns)
        with self.tag("h{}".format(level)):
            if part:
                self.text(
                    self.clean_text(part).strip()
                    + ": "
                    + self.clean_text(title).strip()
                )
            else:
                self.text(self.clean_text(title).strip())

    def get_text(self, item):
        self.text(self.clean_text(item.text))
        for child in item.findall("./*"):
            if child.tag == self.ns_tag("Acronym"):
                with self.tag("abbr", title=child.get("Expansion")):
                    self.text(self.clean_text(child.xpath("string(.)")))
            elif child.tag == self.ns_tag("InlineAmendment"):
                with self.tag("q", klass="amendment"):
                    self.text(self.clean_text(child.xpath("string(.)")).strip('”“"'))
            else:
                self.text(self.clean_text(child.xpath("string(.)")))
            self.text(self.clean_text(child.tail))

    def parse_section_items(self, section, level):
        children = section.xpath("./*", namespaces=self.ns)

        child_section_tags = [
            self.ns_tag("P{}".format(i)) for i in range(level + 1, level + 4)
        ]

        para_tags = [
            self.ns_tag("P{}para".format(i)) for i in range(level, level + 4)
        ] + [self.ns_tag("Para")]

        elements = []

        for item in children:
            if item.tag not in child_section_tags and len(elements) > 0:
                self.parse_section(elements, level + 1)
                elements = []

            if item.tag == self.ns_tag("Text"):
                with self.tag("p"):
                    self.get_text(item)
            elif item.tag == self.ns_tag("AppendText"):
                self.get_text(item)
            elif item.tag == self.ns_tag("UnorderedList"):
                with self.tag("ul"):
                    self.parse_section_items(item, level + 1)
            elif item.tag == self.ns_tag("OrderedList"):
                with self.tag("ol"):
                    self.parse_section_items(item, level + 1)
            elif item.tag == self.ns_tag("ListItem"):
                args = []
                if item.get("NumberOverride"):
                    args.append(("data-number", item.get("NumberOverride")))
                with self.tag("li", *args):
                    self.parse_section_items(item, level + 1)
            elif item.tag in para_tags:
                # Don't increment level here, as we're not entering a list
                self.parse_section_items(item, level)
            elif item.tag == self.ns_tag("Tabular"):
                self.parse_tabular(item)
            elif item.tag == self.ns_tag("BlockAmendment"):
                # BlockAmendment resets level numbering
                with self.tag("blockquote", klass="amendment"):
                    self.parse_blockamendment(item)
            elif item.tag == self.ns_tag("BlockText"):
                self.parse_section_items(item, level)
            elif item.tag == self.ns_tag("Formula"):
                self.parse_mathml(item)
            elif item.tag in child_section_tags:
                elements.append(item)
            elif item.tag == self.ns_tag("ScheduleBody"):
                # Sometimes there's a surprise ScheduleBody at non-root level within a schedule
                self.parse_parts(item, level)
            elif item.tag in (
                self.ns_tag("Pnumber"),
                self.ns_tag("Title"),
                self.ns_tag("TitleBlock"),
                self.ns_tag("Number"),
                self.ns_tag("Reference"),
            ):
                # Handled at the level above
                continue
            else:
                raise Exception("Unknown tag: ", ET.tostring(item))

        if len(elements) > 0:
            self.parse_section(elements, level + 1)

    def parse_blockamendment(self, item):
        # The BlockAmendment tag can contain elements starting at any point of the
        # tree of the legislation being amended, so we have to reset state accordingly.
        if len(item.xpath(
            "./l:P1group|./l:Pblock|./l:Part|./l:Chapter", namespaces=self.ns
        )) > 0:
            self.parse_parts(item, 1)
        elif item.xpath("./l:Tabular|./l:Text", namespaces=self.ns):
            self.parse_section_items(item, 1)
        else:
            self.parse_section(item.xpath("./*", namespaces=self.ns), 1)

    def parse_mathml(self, item):
        math_root = item.find("./m:math", namespaces=self.ns)
        # TODO: this ends up with erroneous namespaces on the root math element but
        # browsers/MathJax don't seem to care.
        self.doc.asis(
            un_namespace(ET.tostring(math_root, method="html", encoding="unicode"))
        )

    def parse_tabular(self, element):
        table = element.find("./html:table", namespaces=self.ns)
        self.doc.asis(ET.tostring(table, method="html", encoding="unicode"))

    def detect_level(self, elements):
        for i in range(1, 6):
            for el in elements:
                if self.ns_tag("P{}".format(i)) == el.tag:
                    return i
        return None

    def parse_section(self, elements, level):
        level = self.detect_level(elements) or level
        with self.tag("ol", klass="p{}".format(level)):
            for element in elements:
                num = element.xpath("string(./l:Pnumber)", namespaces=self.ns)
                if num is None:
                    raise Exception("No number on element")

                tag_args = [("data-number", num)]
                if element.get("id"):
                    tag_args.append(("id", element.get("id")))

                with self.tag("li", *tag_args):
                    self.parse_section_items(element, level)
