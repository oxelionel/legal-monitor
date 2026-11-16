-- Legal Monitor — esquema do banco de dados (SQLite)
-- Gerado a partir de database/models.py (fonte da verdade). A aplicação cria as tabelas
-- automaticamente via SQLAlchemy; este arquivo serve como referência e para criação manual.
-- Compatível com PostgreSQL com ajustes mínimos de tipos (JSON -> JSONB, DATETIME -> TIMESTAMP).

CREATE TABLE audit_log (
	id INTEGER NOT NULL,
	timestamp DATETIME NOT NULL,
	actor VARCHAR(120) NOT NULL,
	action VARCHAR(40) NOT NULL,
	entity VARCHAR(40) NOT NULL,
	entity_id INTEGER,
	description TEXT NOT NULL,
	details JSON,
	is_demo BOOLEAN NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_audit_log_action ON audit_log (action);
CREATE INDEX ix_audit_log_timestamp ON audit_log (timestamp);

CREATE TABLE clients (
	id INTEGER NOT NULL,
	name VARCHAR(200) NOT NULL,
	name_normalized VARCHAR(200) NOT NULL,
	trade_name VARCHAR(200),
	document VARCHAR(14),
	client_type VARCHAR(40) NOT NULL,
	email VARCHAR(200),
	phone VARCHAR(40),
	responsible VARCHAR(120),
	legal_area VARCHAR(80),
	notes TEXT,
	status VARCHAR(20) NOT NULL,
	is_demo BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (document)
);

CREATE INDEX ix_clients_name_normalized ON clients (name_normalized);

CREATE TABLE publications (
	id INTEGER NOT NULL,
	title VARCHAR(300) NOT NULL,
	agency VARCHAR(200) NOT NULL,
	source VARCHAR(120) NOT NULL,
	number VARCHAR(80),
	publication_date DATE NOT NULL,
	legal_area VARCHAR(80) NOT NULL,
	doc_type VARCHAR(80) NOT NULL,
	content TEXT NOT NULL,
	url VARCHAR(500),
	is_demo BOOLEAN NOT NULL,
	last_triaged_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_publications_publication_date ON publications (publication_date);

CREATE TABLE settings (
	"key" VARCHAR(80) NOT NULL,
	value JSON NOT NULL,
	PRIMARY KEY ("key")
);


CREATE TABLE client_keywords (
	id INTEGER NOT NULL,
	client_id INTEGER NOT NULL,
	term VARCHAR(200) NOT NULL,
	term_normalized VARCHAR(200) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_client_keyword UNIQUE (client_id, term_normalized),
	FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE CASCADE
);


CREATE TABLE deadlines (
	id INTEGER NOT NULL,
	description VARCHAR(300) NOT NULL,
	publication_id INTEGER,
	client_id INTEGER,
	date_type VARCHAR(40) NOT NULL,
	reference_date DATE,
	due_date DATE,
	responsible VARCHAR(120),
	status VARCHAR(20) NOT NULL,
	notes TEXT,
	validated BOOLEAN NOT NULL,
	origin VARCHAR(30) NOT NULL,
	is_demo BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(publication_id) REFERENCES publications (id) ON DELETE SET NULL,
	FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE SET NULL
);

CREATE INDEX ix_deadlines_due_date ON deadlines (due_date);

CREATE TABLE matches (
	id INTEGER NOT NULL,
	publication_id INTEGER NOT NULL,
	client_id INTEGER NOT NULL,
	score FLOAT NOT NULL,
	relevance VARCHAR(10) NOT NULL,
	matched_terms JSON NOT NULL,
	justification TEXT NOT NULL,
	status VARCHAR(40) NOT NULL,
	analyst_notes TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_match_pub_client UNIQUE (publication_id, client_id),
	FOREIGN KEY(publication_id) REFERENCES publications (id) ON DELETE CASCADE,
	FOREIGN KEY(client_id) REFERENCES clients (id) ON DELETE CASCADE
);

CREATE INDEX ix_matches_relevance ON matches (relevance);
CREATE INDEX ix_matches_status ON matches (status);
