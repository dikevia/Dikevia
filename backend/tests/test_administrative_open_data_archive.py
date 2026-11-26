from datetime import date

import pytest

from app.legal_ingestion import administrative_open_data_archive_url


@pytest.mark.parametrize(
    ("court", "year", "month", "expected"),
    [
        ("CE", 2026, 10, "https://opendata.justice-administrative.fr/DCE/2026/10/CE_202610.zip"),
        ("CE", 2021, 6, "https://opendata.justice-administrative.fr/DCE/2021/06/CE_202106.zip"),
        ("CAA", 2026, 9, "https://opendata.justice-administrative.fr/DCA/2026/09/CAA_202609.zip"),
        ("TA", 2026, 8, "https://opendata.justice-administrative.fr/DTA/2026/08/TA_202608.zip"),
    ],
)
def test_monthly_archive_url_uses_only_official_fixed_host(court, year, month, expected):
    assert administrative_open_data_archive_url(
        court, year, month, today=date(2026, 11, 25)
    ) == expected


@pytest.mark.parametrize(
    ("court", "year", "month"),
    [
        ("OTHER", 2026, 10),
        ("CE", 2021, 5),
        ("CAA", 2022, 2),
        ("TA", 2022, 5),
        ("TA", 2026, 13),
        ("TA", 2027, 1),
    ],
)
def test_monthly_archive_url_rejects_unknown_or_unavailable_periods(court, year, month):
    with pytest.raises(ValueError):
        administrative_open_data_archive_url(
            court, year, month, today=date(2026, 11, 25)
        )


@pytest.mark.parametrize("year, month", [(True, 1), (2026, False), (2026, 1.5)])
def test_monthly_archive_url_rejects_non_integer_date_parts(year, month):
    with pytest.raises(ValueError):
        administrative_open_data_archive_url("TA", year, month, today=date(2026, 11, 25))
