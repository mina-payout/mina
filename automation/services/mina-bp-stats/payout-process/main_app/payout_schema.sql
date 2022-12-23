-- DROP SCHEMA public;

CREATE SCHEMA public AUTHORIZATION mina_admin;

COMMENT ON SCHEMA public IS 'standard public schema';

-- DROP TYPE public."job_execution_type";

CREATE TYPE public."job_execution_type" AS ENUM (
	'calculation',
	'validation');

-- DROP SEQUENCE public.payout_audit_log_id_seq1;

CREATE SEQUENCE public.payout_audit_log_id_seq1
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;-- public.epoch_delegations definition

-- Drop table

-- DROP TABLE public.epoch_delegations;

CREATE TABLE public.epoch_delegations (
	epoch int4 NULL,
	delegator text NULL,
	delegatee text NULL,
	delegation_amount float8 NULL,
	blocks_produced int4 NULL
);


-- public.payout_audit_log definition

-- Drop table

-- DROP TABLE public.payout_audit_log;

CREATE TABLE public.payout_audit_log (
	id serial4 NOT NULL,
	updated_at timestamp NOT NULL,
	epoch_id int8 NULL,
	ledger_file_name bpchar(200) NULL,
	job_type public."job_execution_type" NOT NULL,
	CONSTRAINT payout_audit_log_pkey PRIMARY KEY (id)
);


-- public.payout_summary definition

-- Drop table

-- DROP TABLE public.payout_summary;

CREATE TABLE public.payout_summary (
	provider_pub_key varchar(280) NOT NULL,
	winner_pub_key varchar(280) NOT NULL,
	blocks int4 NULL,
	payout_amount float8 NULL,
	payout_balance float8 NULL,
	last_delegation_epoch int8 NULL,
	last_slot_validated int8 NULL,
	CONSTRAINT payout_summary_pkey PRIMARY KEY (provider_pub_key, winner_pub_key)
);


-- public.staking_ledger definition

-- Drop table

-- DROP TABLE public.staking_ledger;

CREATE TABLE public.staking_ledger (
	pk varchar(280) NOT NULL,
	balance float8 NULL,
	delegate varchar(280) NOT NULL,
	epoch_number int8 NULL
);


-- public.whitelist definition

-- Drop table

-- DROP TABLE public.whitelist;

CREATE TABLE public.whitelist (
	value varchar(64) NULL
);
