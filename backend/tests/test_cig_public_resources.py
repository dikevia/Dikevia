from app.cig_public_resources import (
    CIG_PUBLIC_RESOURCES,
    get_public_resources_for_theme,
    public_resource_metadata,
)


def test_public_resource_catalog_has_unique_ids_and_metadata_only_status():
    ids = [item.resource_id for item in CIG_PUBLIC_RESOURCES]
    assert len(ids) == len(set(ids))
    assert all(item.content_status == "METADATA_ONLY" for item in CIG_PUBLIC_RESOURCES)


def test_theme_discovery_returns_relevant_cig_resources():
    results = get_public_resources_for_theme("droits_syndicaux")
    assert results
    assert all("droits_syndicaux" in item.themes for item in results)


def test_unknown_or_blank_theme_returns_empty_tuple():
    assert get_public_resources_for_theme(" ") == ()
    assert get_public_resources_for_theme("unknown_theme") == ()


def test_metadata_never_claims_cig_editorial_resource_is_binding_law():
    item = public_resource_metadata("CIG_INFOGRAPHIC_EMPLOIS_FONCTIONNELS")
    assert item is not None
    assert item["legal_weight"] == "NON_BINDING_EDITORIAL_OR_PRACTICAL_RESOURCE"
    assert item["content_status"] == "METADATA_ONLY"
    assert item["publisher"] == "CIG Petite Couronne"


def test_unknown_resource_has_no_metadata():
    assert public_resource_metadata("NOT_A_RESOURCE") is None



def test_union_rights_resource_is_directly_catalogued_with_publication_date():
    item = public_resource_metadata("CIG_SVP_RIGHTS_UNION_ORGANIZATION")
    assert item is not None
    assert item["publication_date"] == "2026-10-16"
    assert "droits_syndicaux" in item["themes"]
    assert item["content_status"] == "METADATA_ONLY"
