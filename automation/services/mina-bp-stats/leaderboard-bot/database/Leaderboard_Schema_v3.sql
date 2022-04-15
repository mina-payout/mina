create database leaderboard_v35

ALTER DATABASE leaderboard_v35 SET timezone TO 'UTC';

-- public.nodes definition

-- Drop table

-- DROP TABLE public.nodes;

CREATE TABLE public.nodes (
	id serial NOT NULL,
	block_producer_key text NULL,
	score int4 NULL,
	score_percent numeric(6,2) NULL,
	updated_at timestamptz NULL,
	discord_id text NULL,
	email_id text NULL,
	application_status bool NULL DEFAULT false,
	CONSTRAINT uq_nodes_block_producer_key_key UNIQUE (block_producer_key),
	CONSTRAINT pk_nodes_pkey PRIMARY KEY (id)
);


--alter table nodes alter column score_percent TYPE  numeric(6,2)
-- public.state_hash definition

-- Drop table
e
-- DROP TABLE public.state_hash;

CREATE TABLE public.statehash (
	id serial NOT NULL,
	value text NULL,
	CONSTRAINT uq_state_hash UNIQUE (value),
	CONSTRAINT pk_state_hash_pkey PRIMARY KEY (id)
);

-- public.uptime_file_history definition

-- Drop table

-- DROP TABLE public.uptime_file_history;

CREATE TABLE public.uptime_file_history (
	id serial NOT NULL,
	file_name text NULL,
	receivedat int8 NULL,
	receivedfrom text NULL,
	node_id int8 NULL,
	block_statehash int4 NULL,
	parent_block_statehash int8 NULL,
	nodedata_blockheight int8 NULL,
	nodedata_slot int8 NULL,
	file_modified_at timestamp NULL,
	file_created_at timestamp NULL,
	file_generation int8 NULL,
	file_crc32c text NULL,
	file_md5_hash text NULL,
	CONSTRAINT pk_uptime_file_history PRIMARY KEY (id),
	CONSTRAINT fk_ufh_nodes FOREIGN KEY (node_id) REFERENCES nodes(id),
	CONSTRAINT fk_ufh_statehash FOREIGN KEY (block_statehash) REFERENCES statehash(id),
	CONSTRAINT fk_ufh_parent_statehash FOREIGN KEY (parent_block_statehash) REFERENCES statehash(id)
);
CREATE INDEX idx_ufh_node_id ON public.uptime_file_history USING btree (node_id);
CREATE INDEX idx_ufh_file_created_at_idx ON public.uptime_file_history USING btree (file_created_at);
CREATE INDEX idx_ufh_file_name ON public.uptime_file_history USING btree (file_name);


-- public.bot_logs definition

-- Drop table
DROP TABLE public.points;
DROP TABLE public.bot_logs_statehash;
DROP TABLE public.bot_logs;

CREATE TABLE public.bot_logs (
	id serial NOT NULL,
	files_processed int4 NULL,
	file_timestamps timestamptz NULL,
	batch_start_epoch int8 NULL,
	batch_end_epoch int8 NULL,
	processing_time float NULL,
	number_of_threads smallint NULL,
	CONSTRAINT pk_bot_logs_pkey PRIMARY KEY (id)
);

-- public.percentile_statehash_table definition

-- Drop table

-- DROP TABLE public.bot_logs_statehash;

CREATE TABLE public.bot_logs_statehash (
	id serial NOT NULL,
	bot_log_id int4 NULL,
	statehash_id int8 NULL,
	parent_statehash_id int8 NULL,
	weight int4 null,
	CONSTRAINT pk_percentile_pkey PRIMARY KEY (id),
	CONSTRAINT fk_bot_log FOREIGN KEY (bot_log_id) REFERENCES bot_logs(id),
	CONSTRAINT fk_bls_statehash FOREIGN KEY (statehash_id) REFERENCES statehash(id),
	CONSTRAINT fk_bls_parent_statehash FOREIGN KEY (parent_statehash_id) REFERENCES statehash(id)
);

-- public.points definition

-- Drop table

-- DROP TABLE public.points;

CREATE TABLE public.points (
	id serial NOT NULL,
	file_name text NULL,
	blockchain_epoch int8 NULL,
	blockchain_height int8 NULL,
	created_at timestamptz NULL,
	amount int4 NULL,
	node_id int4 NULL,
	bot_log_id int4 NULL,
	file_timestamps timestamptz NULL,
	statehash_id int4 NULL,
	CONSTRAINT pk_points_pkey PRIMARY KEY (id),
	CONSTRAINT fk_bot_log FOREIGN KEY (bot_log_id) REFERENCES bot_logs(id),
	CONSTRAINT fk_nodes FOREIGN KEY (node_id) REFERENCES nodes(id),
	CONSTRAINT fk_statehash FOREIGN KEY (statehash_id) REFERENCES statehash(id)
);
CREATE INDEX idx_points_file_timestamps_idx ON public.points USING btree (file_timestamps);


	INSERT INTO public.bot_logs
	(files_processed, file_timestamps, batch_start_epoch, batch_end_epoch, processing_time, number_of_threads)
	VALUES(0, '2022-03-23 00:00:00+00', 1647993600, 1647993600, 0, 0);