class ConversionReport:
    def __init__(self):
        self.replaced = []
        self.unmatched = []
        self.custom_colors = {}
        self.warnings = []
        self.disambiguated = []
        self.missing_conn_collider = []

    def to_html(self) -> str:
        rows = "".join("<tr><td>{}</td><td>{}</td></tr>".format(r[0], r[1])
                       for r in self.replaced[:200])
        um = "".join("<li>{}</li>".format(m.design_id) for m in self.unmatched)
        cc = "".join("<li>{}: {} ({},{},{})</li>".format(
            k, v[0], v[1], v[2], v[3]) for k, v in self.custom_colors.items())
        dis = "".join("<li>{} → {}</li>".format(a, b)
                      for a, b in self.disambiguated[:200])
        mc = "".join("<li>{}</li>".format(i) for i in self.missing_conn_collider)
        return (
            "<html><body><h1>转换报告</h1>"
            "<h2>替换 ({})</h2><table>{}</table>"
            "<h2>消歧 ({})</h2><ul>{}</ul>"
            "<h2>未匹配 ({})</h2><ul>{}</ul>"
            "<h2>自定义色 ({})</h2><ul>{}</ul>"
            "<h2>缺连接点/碰撞体积 ({})</h2><ul>{}</ul>"
            "</body></html>").format(
                len(self.replaced), rows, len(self.disambiguated), dis,
                len(self.unmatched), um, len(self.custom_colors), cc,
                len(self.missing_conn_collider), mc)
