-- Migration 032: source provenance, reuse permissions and controlled refresh policy.
BEGIN;

CREATE TABLE legal_source_registry (
    source_key text PRIMARY KEY,
    display_name text NOT NULL,
    source_type text NOT NULL,
    authority_level text NOT NULL CHECK (authority_level IN (
        'PRIMARY_LAW','OFFICIAL_JURISPRUDENCE','OFFICIAL_ADMIN_GUIDANCE',
        'PROFESSIONAL_GUIDANCE','TRADE_UNION_POSITION','SECONDARY_DOCTRINE',
        'COMPETITOR','UNKNOWN'
    )),
    publisher text,
    homepage_url text,
    access_mode text NOT NULL CHECK (access_mode IN (
        'API','OPEN_DATA_BULK','OPEN_DATASET','MANUAL_LINK','MANUAL_APPROVED','EXCLUDED'
    )),
    license_name text,
    license_url text,
    terms_url text,
    reuse_basis text NOT NULL DEFAULT 'NOT_ASSESSED' CHECK (reuse_basis IN (
        'OPEN_LICENSE','OWNER_APPROVED_PENDING_REVIEW','METADATA_ONLY',
        'MANUAL_PERMISSION_REQUIRED','NOT_AUTHORIZED','NOT_ASSESSED'
    )),
    automated_fetch_allowed boolean NOT NULL DEFAULT false,
    metadata_ingestion_allowed boolean NOT NULL DEFAULT true,
    full_text_ingestion_allowed boolean NOT NULL DEFAULT false,
    commercial_reuse_allowed boolean NOT NULL DEFAULT false,
    attribution_required boolean NOT NULL DEFAULT true,
    verification_status text NOT NULL DEFAULT 'PENDING' CHECK (verification_status IN (
        'VERIFIED','CONDITIONAL','PENDING','RESTRICTED','EXCLUDED'
    )),
    refresh_policy text NOT NULL DEFAULT 'MANUAL_REVIEW',
    notes text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (homepage_url IS NULL OR homepage_url LIKE 'https://%')
);

CREATE INDEX legal_source_registry_authority_idx
    ON legal_source_registry(authority_level, verification_status);
CREATE INDEX legal_source_registry_fetch_idx
    ON legal_source_registry(automated_fetch_allowed, verification_status);

INSERT INTO legal_source_registry (
    source_key, display_name, source_type, authority_level, publisher, homepage_url,
    access_mode, license_name, license_url, terms_url, reuse_basis,
    automated_fetch_allowed, metadata_ingestion_allowed, full_text_ingestion_allowed,
    commercial_reuse_allowed, verification_status, refresh_policy, notes
) VALUES
(
    'LEGIFRANCE_PISTE','Légifrance — API PISTE','LEGIFRANCE',
    'PRIMARY_LAW','DILA','https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api',
    'API','Licence Ouverte 2.0',
    'https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api',
    'https://www.legifrance.gouv.fr/contenu/Media/files/pied-de-page/cgu-legifrance-api-vf-15-12-2022_0.pdf',
    'OPEN_LICENSE',true,true,true,true,'VERIFIED','INCREMENTAL_API_WITH_QUOTA',
    'API gratuite après inscription PISTE. Respecter les quotas par jeton et les CGU. Ne jamais exposer les clés API.'
),
(
    'JUSTICE_ADMIN_OPEN_DATA','Justice administrative — Open Data CE/CAA/TA','OTHER_OFFICIAL',
    'OFFICIAL_JURISPRUDENCE','Conseil d''État','https://opendata.justice-administrative.fr/',
    'OPEN_DATA_BULK','Licence Ouverte 2.0',
    'https://conseil-etat.fr/decisions-de-justice/donnees-ouvertes-open-data',
    'https://conseil-etat.fr/decisions-de-justice/donnees-ouvertes-open-data',
    'OPEN_LICENSE',true,true,true,true,'VERIFIED','MONTHLY_ARCHIVE_INCREMENTAL',
    'Décisions XML CE depuis 30/09/2021, CAA depuis 31/03/2022 et TA depuis 30/06/2022. Conserver les identifiants, dates, juridictions, occultations et archive d’origine.'
),
(
    'SERVICE_PUBLIC_DATA','Service-Public.fr — jeu de données DILA','SERVICE_PUBLIC_PART',
    'OFFICIAL_ADMIN_GUIDANCE','DILA','https://www.service-public.gouv.fr/P10004',
    'OPEN_DATASET','Licence Ouverte / Open Licence',
    'https://www.service-public.gouv.fr/P10004',
    'https://www.data.gouv.fr/fr/datasets/service-public-fr-guide-vos-droits-et-demarches-professionnels-entreprises',
    'OPEN_LICENSE',true,true,true,true,'VERIFIED','WEEKLY_OR_DATASET_UPDATE',
    'Fiches pratiques de vulgarisation. Toujours conserver attribution et date de mise à jour. Ne jamais traiter ces fiches comme source normative primaire.'
),
(
    'DGAFP','DGAFP — ressources sélectionnées de la fonction publique','INSTITUTIONAL_GUIDANCE',
    'OFFICIAL_ADMIN_GUIDANCE','DGAFP','https://www.fonction-publique.gouv.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','APPROVED_SEEDS_ONLY',
    'Le registre documentaire du projet identifie des ressources sélectionnées comme réutilisables. L''ingestion du texte intégral est conditionnée au statut REUSE_APPROVED de la fiche individuelle et à la validation de son champ FPT/FPE.'
),
(
    'CNFPT','CNFPT — ressources sélectionnées de la fonction publique territoriale','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','CNFPT','https://www.cnfpt.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','APPROVED_SEEDS_ONLY',
    'Le registre documentaire du projet identifie des ressources sélectionnées comme réutilisables. L''ingestion du texte intégral est conditionnée au statut REUSE_APPROVED de la fiche individuelle et à la validation de son champ FPT.'
),
(
    'INFO_GOUV','Info.gouv.fr — ressources textuelles sélectionnées','INSTITUTIONAL_GUIDANCE',
    'OFFICIAL_ADMIN_GUIDANCE','Service d''information du Gouvernement','https://www.info.gouv.fr/',
    'MANUAL_APPROVED',NULL,NULL,'https://www.info.gouv.fr/mentions-legales',
    'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','APPROVED_SEEDS_ONLY',
    'Les conditions de réutilisation sont documentées dans le registre du projet pour quatre ressources sélectionnées uniquement. Aucune aspiration générale du domaine ; exclure les éléments de tiers.'
),
(
    'DILA_CIRCULAIRES','DILA — fonds des circulaires','DILA_CIRCULAIRES',
    'OFFICIAL_ADMIN_GUIDANCE','DILA','https://www.legifrance.gouv.fr/',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Parser XML présent dans le dépôt. Réutilisation du texte intégral et conditions du jeu de données à confirmer avant automatisation.'
),
(
    'ARIANEWEB','Conseil d''État — ArianeWeb','ARIANEWEB',
    'OFFICIAL_JURISPRUDENCE','Conseil d''État','https://conseil-etat.fr/site/decisions-de-justice/jurisprudence/rechercher-une-decision-arianeweb',
    'MANUAL_LINK',NULL,NULL,
    'https://www.conseil-etat.fr/decisions-de-justice/jurisprudence/rechercher-une-decision-arianeweb/se-procurer-une-decision-ou-des-conclusions-d-un-rapporteur-public',
    'METADATA_ONLY',false,true,false,false,'CONDITIONAL','MANUAL_REVIEW',
    'Base de sélection de décisions, analyses et conclusions. Pas d’aspiration massive des analyses ou conclusions sans autorisation explicite. Pour le texte des décisions, privilégier Légifrance et Open Data.'
),
(
    'DGAFP_CIRCULAIRES','DGAFP — circulaires fonction publique','INSTITUTIONAL_GUIDANCE',
    'OFFICIAL_ADMIN_GUIDANCE','DGAFP','https://www.fonction-publique.gouv.fr/droit-de-la-fonction-publique/actualites-du-droit-de-la-fonction-publique/circulaires-fonction-publique',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Référentiel de circulaires annoncées en vigueur. Vérifier le versant, le caractère opposable et la version avant usage.'
),
(
    'DGAFP_DOCUMENTS_OPPOSABLES','DGAFP — documents opposables','INSTITUTIONAL_GUIDANCE',
    'OFFICIAL_ADMIN_GUIDANCE','DGAFP','https://www.fonction-publique.gouv.fr/droit-de-la-fonction-publique/actualites-du-droit-de-la-fonction-publique/documents-opposables',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Conserver la référence, la date et le champ d’application. Vérifier si le document est opposable et si son champ couvre la FPT.'
),
(
    'DGAFP_VIGIE','DGAFP — archives Vigie','INSTITUTIONAL_GUIDANCE',
    'OFFICIAL_ADMIN_GUIDANCE','DGAFP','https://www.fonction-publique.gouv.fr/lettres-dinformation',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Veille juridique utile, mais secondaire par rapport aux textes et décisions cités. Pas d’aspiration intégrale sans conditions de réutilisation vérifiées.'
),
(
    'CGFP_SNAPSHOT','CGFP — instantané documentaire','CGFP_SNAPSHOT',
    'PRIMARY_LAW','Légifrance','https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000044416551/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'NOT_ASSESSED',false,true,false,false,
    'PENDING','MANUAL_REVALIDATION',
    'Instantané PDF importé dans le corpus. Provenance et correspondance article/version à vérifier avec PISTE avant de qualifier les textes comme en vigueur.'
),
(
    'CNFPT_WIKITERRITORIAL','CNFPT — Wikiterritorial et ressources','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','CNFPT','https://inet.cnfpt.fr/ressources/ressources-metiers-cnfpt/wikiterritorial',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'PENDING','MANUAL_REVIEW',
    'Ressources pédagogiques consultables librement. Conditions de réutilisation des contenus à vérifier document par document.'
),
(
    'CDG35','CDG 35 — ressources statutaires et RH','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','Centre de gestion d''Ille-et-Vilaine','https://www.cdg35.bzh/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Des documents sont déjà présents avec réutilisation approuvée par le responsable du projet. Vérifier les droits et conserver la validation juridique distincte.'
),
(
    'CDG59','CDG 59 — ressources statutaires et RH','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','Centre de gestion du Nord','https://www.cdg59.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Des documents sont déjà présents avec réutilisation approuvée par le responsable du projet. Vérifier les droits et conserver la validation juridique distincte.'
),
(
    'CDG69','CDG 69 — ressources statutaires et RH','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','Centre de gestion du Rhône et de la Métropole de Lyon','https://www.cdg69.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Des documents sont déjà présents avec réutilisation approuvée par le responsable du projet. Vérifier les droits et conserver la validation juridique distincte.'
),
(
    'CIG_PETITE_COURONNE','CIG Petite Couronne — ressources statutaires','INSTITUTIONAL_GUIDANCE',
    'PROFESSIONAL_GUIDANCE','CIG Petite Couronne','https://www.cig929394.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Ressources professionnelles. Vérifier les droits de réutilisation de chaque document.'
),
(
    'CFDT_INTERCO','CFDT Interco — ressources syndicales','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','CFDT Interco','https://www.cfdt-interco31.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Position et documentation syndicales. Distinguer revendication, analyse et droit positif. Vérifier les droits sur chaque document.'
),
(
    'CFDT_UFFA','CFDT Fonctions Publiques — UFFA','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','CFDT Fonctions Publiques','https://uffa.cfdt.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW',
    'Position et documentation syndicales. Distinguer revendication, analyse et droit positif. Vérifier les droits sur chaque document.'
),
(
    'CFTC_FONCTION_PUBLIQUE','CFTC — Fonction publique','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','CFTC','https://www.cftc.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW','Source syndicale secondaire ; ne pas assimiler à une source normative.'
),
(
    'CGT_FONCTION_PUBLIQUE','CGT — Fonction publique','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','CGT','https://www.cgt.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW','Source syndicale secondaire ; ne pas assimiler à une source normative.'
),
(
    'FO_FONCTION_PUBLIQUE','FO — Fonction publique','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','FO','https://www.force-ouvriere.fr/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW','Source syndicale secondaire ; ne pas assimiler à une source normative.'
),
(
    'SOLIDAIRES_FONCTION_PUBLIQUE','Solidaires — Fonction publique','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','Solidaires','https://www.solidaires.org/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW','Source syndicale secondaire ; ne pas assimiler à une source normative.'
),
(
    'UNSA_FONCTION_PUBLIQUE','UNSA — Fonction publique','INSTITUTIONAL_GUIDANCE',
    'TRADE_UNION_POSITION','UNSA','https://www.unsa.org/',
    'MANUAL_APPROVED',NULL,NULL,NULL,'OWNER_APPROVED_PENDING_REVIEW',false,true,true,false,
    'CONDITIONAL','MANUAL_REVIEW','Source syndicale secondaire ; ne pas assimiler à une source normative.'
),
(
    'LANDOT','Cabinet Landot — veille juridique','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','Landot & Associés','https://www.landot-avocats.net/',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW','Doctrine secondaire ; lien et métadonnées uniquement sans licence ou autorisation explicite.'
),
(
    'GAZETTE_COMMUNES','La Gazette des communes','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','Groupe Moniteur','https://www.lagazettedescommunes.com/',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'RESTRICTED','MANUAL_REVIEW','Contenus éditoriaux susceptibles de droits et d’accès payant. Aucun stockage du texte intégral sans licence.'
),
(
    'LOCALtis','Localtis — Banque des Territoires','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','Banque des Territoires','https://www.banquedesterritoires.fr/localtis',
    'MANUAL_LINK',NULL,NULL,NULL,'METADATA_ONLY',false,true,false,false,
    'CONDITIONAL','MANUAL_REVIEW','Contenus éditoriaux secondaires ; lien et métadonnées uniquement sans licence explicite.'
),
(
    'WEKA','WEKA — documentation professionnelle','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','WEKA','https://www.weka.fr/',
    'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',false,false,false,false,
    'RESTRICTED','EXCLUDED','Contenu payant ou sous licence. Exclu de toute ingestion sans contrat explicite.'
),
(
    'DALLOZ','Dalloz — documentation juridique','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','Dalloz','https://www.dalloz.fr/',
    'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',false,false,false,false,
    'RESTRICTED','EXCLUDED','Contenu éditorial protégé ou sous abonnement. Exclu de toute ingestion sans contrat explicite.'
),
(
    'LEXISNEXIS','LexisNexis — documentation juridique','SECONDARY_DOCTRINE',
    'SECONDARY_DOCTRINE','LexisNexis','https://www.lexisnexis.com/',
    'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',false,false,false,false,
    'RESTRICTED','EXCLUDED','Contenu éditorial protégé ou sous abonnement. Exclu de toute ingestion sans contrat explicite.'
),
(
    'DELIBIA','Delibia — produit concurrent','COMPETITOR',
    'COMPETITOR','Delibia',NULL,'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',
    false,false,false,false,'EXCLUDED','EXCLUDED','Concurrent : aucune collecte ni réutilisation de contenu ou de données.'
),
(
    'COMMUNIA','Communia — produit concurrent','COMPETITOR',
    'COMPETITOR','Communia',NULL,'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',
    false,false,false,false,'EXCLUDED','EXCLUDED','Concurrent : aucune collecte ni réutilisation de contenu ou de données.'
),
(
    'KOLECTIVIA','Kolectivia — produit concurrent','COMPETITOR',
    'COMPETITOR','Kolectivia',NULL,'EXCLUDED',NULL,NULL,NULL,'NOT_AUTHORIZED',
    false,false,false,false,'EXCLUDED','EXCLUDED','Concurrent : aucune collecte ni réutilisation de contenu ou de données.'
)
ON CONFLICT (source_key) DO UPDATE SET
    display_name=EXCLUDED.display_name,
    source_type=EXCLUDED.source_type,
    authority_level=EXCLUDED.authority_level,
    publisher=EXCLUDED.publisher,
    homepage_url=EXCLUDED.homepage_url,
    access_mode=EXCLUDED.access_mode,
    license_name=EXCLUDED.license_name,
    license_url=EXCLUDED.license_url,
    terms_url=EXCLUDED.terms_url,
    reuse_basis=EXCLUDED.reuse_basis,
    automated_fetch_allowed=EXCLUDED.automated_fetch_allowed,
    metadata_ingestion_allowed=EXCLUDED.metadata_ingestion_allowed,
    full_text_ingestion_allowed=EXCLUDED.full_text_ingestion_allowed,
    commercial_reuse_allowed=EXCLUDED.commercial_reuse_allowed,
    attribution_required=EXCLUDED.attribution_required,
    verification_status=EXCLUDED.verification_status,
    refresh_policy=EXCLUDED.refresh_policy,
    notes=EXCLUDED.notes,
    updated_at=now();

ALTER TABLE legal_documents
    ADD COLUMN source_key text REFERENCES legal_source_registry(source_key);
ALTER TABLE legal_ingestion_runs
    ADD COLUMN source_key text REFERENCES legal_source_registry(source_key);

UPDATE legal_documents
SET source_key = CASE
    WHEN source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT','LEGIFRANCE_JORF')
        THEN 'LEGIFRANCE_PISTE'
    WHEN source_type = 'CGFP_SNAPSHOT' THEN 'CGFP_SNAPSHOT'
    WHEN source_type = 'SERVICE_PUBLIC_PART' THEN 'SERVICE_PUBLIC_DATA'
    WHEN source_type = 'OTHER_OFFICIAL'
         AND raw_metadata->>'import_method' = 'JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML'
        THEN 'JUSTICE_ADMIN_OPEN_DATA'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cdg-35' THEN 'CDG35'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cdg-59' THEN 'CDG59'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cdg-69' THEN 'CDG69'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cig-petite-couronne' THEN 'CIG_PETITE_COURONNE'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cnfpt' THEN 'CNFPT'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'dgafp' THEN 'DGAFP'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'info-gouv' THEN 'INFO_GOUV'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cfdt-interco' THEN 'CFDT_INTERCO'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cfdt-fonctions-publiques' THEN 'CFDT_UFFA'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cftc-fonction-publique' THEN 'CFTC_FONCTION_PUBLIQUE'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'cgt-fonction-publique' THEN 'CGT_FONCTION_PUBLIQUE'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'fo-fonction-publique' THEN 'FO_FONCTION_PUBLIQUE'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'solidaires-fonction-publique' THEN 'SOLIDAIRES_FONCTION_PUBLIQUE'
    WHEN source_type = 'INSTITUTIONAL_GUIDANCE' AND raw_metadata->>'source_id' = 'unsa-fonction-publique' THEN 'UNSA_FONCTION_PUBLIQUE'
    ELSE NULL
END
WHERE source_key IS NULL;

UPDATE legal_ingestion_runs
SET source_key = CASE
    WHEN source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT','LEGIFRANCE_JORF') THEN 'LEGIFRANCE_PISTE'
    WHEN source_type = 'DILA_CIRCULAIRES' THEN 'DILA_CIRCULAIRES'
    WHEN source_type = 'SERVICE_PUBLIC_PART' THEN 'SERVICE_PUBLIC_DATA'
    WHEN source_type = 'CGFP_SNAPSHOT' THEN 'CGFP_SNAPSHOT'
    ELSE NULL
END
WHERE source_key IS NULL;

CREATE INDEX legal_documents_source_key_idx ON legal_documents(source_key);
CREATE INDEX legal_ingestion_runs_source_key_idx ON legal_ingestion_runs(source_key);

CREATE OR REPLACE FUNCTION legal_ingestion_runs_assign_source_key()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.source_key IS NULL THEN
        NEW.source_key := CASE
            WHEN NEW.source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT','LEGIFRANCE_JORF') THEN 'LEGIFRANCE_PISTE'
            WHEN NEW.source_type = 'DILA_CIRCULAIRES' THEN 'DILA_CIRCULAIRES'
            WHEN NEW.source_type = 'SERVICE_PUBLIC_PART' THEN 'SERVICE_PUBLIC_DATA'
            WHEN NEW.source_type = 'CGFP_SNAPSHOT' THEN 'CGFP_SNAPSHOT'
            ELSE NULL
        END;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER legal_ingestion_runs_assign_source_key_trigger
BEFORE INSERT ON legal_ingestion_runs
FOR EACH ROW EXECUTE FUNCTION legal_ingestion_runs_assign_source_key();

GRANT SELECT ON legal_source_registry TO cfdt_juris_app;
GRANT SELECT, INSERT, UPDATE ON legal_source_registry TO cfdt_juris_ingest;
GRANT SELECT, INSERT, UPDATE ON legal_ingestion_runs TO cfdt_juris_ingest;

COMMIT;
