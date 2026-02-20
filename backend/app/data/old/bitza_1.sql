PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version VALUES('81487167e00c');
CREATE TABLE IF NOT EXISTS "users" (
	id INTEGER NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	display_name VARCHAR(50) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	is_superuser BOOLEAN NOT NULL, 
	updated_at DATETIME, 
	CONSTRAINT pk_users PRIMARY KEY (id)
);
INSERT INTO users VALUES(1,'tim.bowden@mapforge.com.au','Tim',1,'2026-02-04 07:06:40','x',1,NULL);
INSERT INTO users VALUES(2,'joshua.w.bowden@gmail.com','Joshua',0,'2026-02-04 07:06:40','x',0,NULL);
INSERT INTO users VALUES(3,'jamesb1847@gmail.com','James',0,'2026-02-04 07:06:40','x',0,NULL);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_display_name ON users (display_name);
COMMIT;
