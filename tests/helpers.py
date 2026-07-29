"""Test config factory: builds a config.toml pointing all lists at local
fixtures via file:// URLs, plus shared fixture paths."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

SANCTIONED_EVM = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
CLEAN_EVM = "0x1111111111111111111111111111111111111111"

CONFIG_TEMPLATE = """
[agent]
security_contact = "Test Security Contact (@sectest)"
checklist_ref = "Checklist v1, item 9"

[screening]
max_list_age_hours = 24
name_hit_threshold = 0.95
name_review_threshold = 0.85
data_dir = "{data_dir}"
reports_dir = "{reports_dir}"

[[lists]]
id = "ofac_sdn"
name = "OFAC SDN List"
url = "{ofac_url}"
format = "ofac_xml"
required = true

[[lists]]
id = "un_consolidated"
name = "UN Consolidated"
url = "{un_url}"
format = "un_xml"
required = true

[[lists]]
id = "eu_fsd"
name = "EU FSD"
url = "{eu_url}"
format = "eu_fsd_xml"
required = true

[[lists]]
id = "uk_ofsi"
name = "UK OFSI"
url = "{uk_url}"
format = "uk_ofsi_xml"
required = true

[risk.chainabuse]
enabled = false
required = false

[risk.etherscan_proximity]
enabled = false
required = false

[risk.known_sets]
enabled = true
required = true
"""


def make_config(tmp_path: Path, ofac_url: str | None = None) -> Path:
    cfg = CONFIG_TEMPLATE.format(
        data_dir=str(tmp_path / "lists"),
        reports_dir=str(tmp_path / "reports"),
        ofac_url=ofac_url or (FIXTURES / "ofac_fixture.xml").as_uri(),
        un_url=(FIXTURES / "un_fixture.xml").as_uri(),
        eu_url=(FIXTURES / "eu_fixture.xml").as_uri(),
        uk_url=(FIXTURES / "uk_fixture.xml").as_uri(),
    )
    path = tmp_path / "config.toml"
    path.write_text(cfg)
    return path
