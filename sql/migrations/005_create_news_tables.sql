CREATE TABLE IF NOT EXISTS news_documents (
    document_id VARCHAR PRIMARY KEY,
    published_at TIMESTAMP,
    available_from TIMESTAMP NOT NULL,
    retrieved_at TIMESTAMP NOT NULL,
    source VARCHAR NOT NULL,
    headline VARCHAR,
    body_text VARCHAR,
    language VARCHAR,
    url_hash VARCHAR,
    payload_hash VARCHAR,
    raw_archive_path VARCHAR
);

CREATE TABLE IF NOT EXISTS news_security_map (
    document_id VARCHAR NOT NULL,
    security_id VARCHAR NOT NULL,
    relevance_score DOUBLE,
    mapping_method VARCHAR,
    model_version VARCHAR,
    calculated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (
        document_id,
        security_id,
        model_version
    )
);
