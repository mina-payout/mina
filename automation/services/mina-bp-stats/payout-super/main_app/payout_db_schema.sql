-- public.bp_wallet_mapping definition

-- Drop table

-- DROP TABLE public.bp_wallet_mapping;

CREATE TABLE public.bp_wallet_mapping (
	provider_wallet_name varchar(64) NULL,
	provider_key varchar(64) NULL,
	return_wallet_key varchar(64) NULL,
	bp_key varchar(64) NULL,
	bp_email varchar(50) NULL,
	wallet0 varchar(64) NULL,
	wallet1 varchar(64) NULL,
	wallet2 varchar(64) NULL,
	wallet3 varchar(64) NULL,
	wallet4 varchar(64) NULL,
	wallet5 varchar(64) NULL,
	wallet6 varchar(64) NULL,
	wallet7 varchar(64) NULL,
	wallet8 varchar(64) NULL,
	wallet9 varchar(64) NULL,
	wallet10 varchar(64) NULL,
	epoch int2 NULL
);
CREATE UNIQUE INDEX idx_bwm_1 ON public.bp_wallet_mapping USING btree (provider_key, epoch);


-- public.mf_wallets definition

-- Drop table

-- DROP TABLE public.mf_wallets;

CREATE TABLE public.mf_wallets (
	asset varchar(50) NULL,
	"key_type" varchar(50) NULL,
	info varchar(50) NULL,
	address varchar(64) NULL,
	status varchar(50) NULL,
	balance int4 NULL,
	created_at varchar(50) NULL,
	created_by varchar(50) NULL
);


-- public.payout_audit_log definition

-- Drop table

-- DROP TABLE public.payout_audit_log;

CREATE TABLE public.payout_audit_log (
	id serial4 NOT NULL,
	updated_at timestamp NOT NULL,
	epoch_id int8 NULL,
	ledger_file_name bpchar(200) NULL,
	job_type public.job_execution_type NOT NULL,
	CONSTRAINT payout_audit_log_pkey PRIMARY KEY (id)
);


-- public.payout_summary definition

-- Drop table

-- DROP TABLE public.payout_summary;

CREATE TABLE public.payout_summary (
	provider_key varchar(64) NOT NULL,
	bp_key varchar(64) NOT NULL,
	blocks_produced int4 NULL,
	payout_amount float8 NULL,
	payout_balance float8 NULL,
	blocks_won int4 NULL,
	burn_amount float8 NULL,
	burn_balance float8 NULL,
	epoch int2 NOT NULL,
	last_delegation_epoch int8 NULL,
	last_slot_validated int8 NULL,
	CONSTRAINT payout_summary_pkey PRIMARY KEY (provider_key, bp_key, epoch)
);


-- public.staking_ledger definition

-- Drop table

-- DROP TABLE public.staking_ledger;

CREATE TABLE public.staking_ledger (
	provider_key varchar(64) NOT NULL,
	bp_key varchar(64) NOT NULL,
	balance float8 NULL,
	epoch int2 NULL
);
CREATE UNIQUE INDEX idx_staking_ledger_1 ON public.staking_ledger USING btree (provider_key, bp_key, epoch);


-- public.whitelist definition

-- Drop table

-- DROP TABLE public.whitelist;

CREATE TABLE public.whitelist (
	value varchar(64) NULL
);