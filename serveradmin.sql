--
-- PostgreSQL database dump
--

-- Dumped from database version 14.2 (Debian 14.2-1.pgdg110+1)
-- Dumped by pg_dump version 14.3 (Debian 14.3-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: access_control_group; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.access_control_group (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    query character varying(1000) NOT NULL,
    is_whitelist boolean NOT NULL
);


ALTER TABLE public.access_control_group OWNER TO serveradmin;

--
-- Name: access_control_group_applications; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.access_control_group_applications (
    id integer NOT NULL,
    accesscontrolgroup_id integer NOT NULL,
    application_id integer NOT NULL
);


ALTER TABLE public.access_control_group_applications OWNER TO serveradmin;

--
-- Name: access_control_group_applications_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.access_control_group_applications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.access_control_group_applications_id_seq OWNER TO serveradmin;

--
-- Name: access_control_group_applications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.access_control_group_applications_id_seq OWNED BY public.access_control_group_applications.id;


--
-- Name: access_control_group_attributes; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.access_control_group_attributes (
    id integer NOT NULL,
    accesscontrolgroup_id integer NOT NULL,
    attribute_id character varying(32) NOT NULL
);


ALTER TABLE public.access_control_group_attributes OWNER TO serveradmin;

--
-- Name: access_control_group_attributes_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.access_control_group_attributes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.access_control_group_attributes_id_seq OWNER TO serveradmin;

--
-- Name: access_control_group_attributes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.access_control_group_attributes_id_seq OWNED BY public.access_control_group_attributes.id;


--
-- Name: access_control_group_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.access_control_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.access_control_group_id_seq OWNER TO serveradmin;

--
-- Name: access_control_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.access_control_group_id_seq OWNED BY public.access_control_group.id;


--
-- Name: access_control_group_members; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.access_control_group_members (
    id integer NOT NULL,
    accesscontrolgroup_id integer NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE public.access_control_group_members OWNER TO serveradmin;

--
-- Name: access_control_group_members_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.access_control_group_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.access_control_group_members_id_seq OWNER TO serveradmin;

--
-- Name: access_control_group_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.access_control_group_members_id_seq OWNED BY public.access_control_group_members.id;


--
-- Name: api_lock; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.api_lock (
    id integer NOT NULL,
    hash_sum character varying(40) NOT NULL,
    until timestamp with time zone,
    duration integer,
    CONSTRAINT api_lock_duration_check CHECK ((duration >= 0))
);


ALTER TABLE public.api_lock OWNER TO serveradmin;

--
-- Name: api_lock_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.api_lock_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.api_lock_id_seq OWNER TO serveradmin;

--
-- Name: api_lock_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.api_lock_id_seq OWNED BY public.api_lock.id;


--
-- Name: apps_application; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.apps_application (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    app_id character varying(64) NOT NULL,
    auth_token character varying(64) NOT NULL,
    location character varying(150) NOT NULL,
    disabled boolean NOT NULL,
    superuser boolean NOT NULL,
    allowed_methods text NOT NULL,
    owner_id integer NOT NULL,
    last_login timestamp with time zone
);


ALTER TABLE public.apps_application OWNER TO serveradmin;

--
-- Name: apps_application_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.apps_application_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.apps_application_id_seq OWNER TO serveradmin;

--
-- Name: apps_application_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.apps_application_id_seq OWNED BY public.apps_application.id;


--
-- Name: apps_publickey; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.apps_publickey (
    key_algorithm character varying(80) NOT NULL,
    key_base64 character varying(2048) NOT NULL,
    key_comment character varying(80) NOT NULL,
    application_id integer NOT NULL
);


ALTER TABLE public.apps_publickey OWNER TO serveradmin;

--
-- Name: attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.attribute (
    attribute_id character varying(32) NOT NULL,
    type character varying(32) NOT NULL,
    multi boolean NOT NULL,
    hovertext text NOT NULL,
    "group" character varying(32) NOT NULL,
    help_link character varying(255),
    readonly boolean NOT NULL,
    clone boolean NOT NULL,
    regexp character varying(1024) NOT NULL,
    reversed_attribute_id character varying(32),
    target_servertype_id character varying(32),
    CONSTRAINT attribute_attribute_id_check CHECK (((attribute_id)::text ~ '\A[a-z][a-z0-9_]+\Z'::text)),
    CONSTRAINT attribute_clone_check CHECK (((NOT clone) OR ((type)::text <> ALL ((ARRAY['reverse'::character varying, 'supernet'::character varying, 'domain'::character varying])::text[])))),
    CONSTRAINT attribute_multi_check CHECK ((((type)::text <> ALL ((ARRAY['boolean'::character varying, 'supernet'::character varying, 'domain'::character varying])::text[])) OR (NOT multi))),
    CONSTRAINT attribute_readonly_check CHECK ((((type)::text <> ALL ((ARRAY['reverse'::character varying, 'supernet'::character varying, 'domain'::character varying])::text[])) OR readonly)),
    CONSTRAINT attribute_regexp_check CHECK (((regexp)::text ~ '\A\\A.*\\Z\Z'::text)),
    CONSTRAINT attribute_reversed_attribute_id_check CHECK ((((type)::text = 'reverse'::text) = (reversed_attribute_id IS NOT NULL))),
    CONSTRAINT attribute_target_servertype_id_check CHECK ((((type)::text = ANY ((ARRAY['relation'::character varying, 'supernet'::character varying, 'domain'::character varying])::text[])) = (target_servertype_id IS NOT NULL)))
);


ALTER TABLE public.attribute OWNER TO serveradmin;

--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


ALTER TABLE public.auth_group OWNER TO serveradmin;

--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_group_id_seq OWNER TO serveradmin;

--
-- Name: auth_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_group_id_seq OWNED BY public.auth_group.id;


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_group_permissions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_group_permissions OWNER TO serveradmin;

--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_group_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_group_permissions_id_seq OWNER TO serveradmin;

--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_group_permissions_id_seq OWNED BY public.auth_group_permissions.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


ALTER TABLE public.auth_permission OWNER TO serveradmin;

--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_permission_id_seq OWNER TO serveradmin;

--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_permission_id_seq OWNED BY public.auth_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


ALTER TABLE public.auth_user OWNER TO serveradmin;

--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_user_groups (
    id integer NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


ALTER TABLE public.auth_user_groups OWNER TO serveradmin;

--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_user_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_groups_id_seq OWNER TO serveradmin;

--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_user_groups_id_seq OWNED BY public.auth_user_groups.id;


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_id_seq OWNER TO serveradmin;

--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.auth_user_user_permissions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_user_user_permissions OWNER TO serveradmin;

--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.auth_user_user_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_user_permissions_id_seq OWNER TO serveradmin;

--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.auth_user_user_permissions_id_seq OWNED BY public.auth_user_user_permissions.id;


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id integer NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


ALTER TABLE public.django_admin_log OWNER TO serveradmin;

--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.django_admin_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_admin_log_id_seq OWNER TO serveradmin;

--
-- Name: django_admin_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.django_admin_log_id_seq OWNED BY public.django_admin_log.id;


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


ALTER TABLE public.django_content_type OWNER TO serveradmin;

--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.django_content_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_content_type_id_seq OWNER TO serveradmin;

--
-- Name: django_content_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.django_content_type_id_seq OWNED BY public.django_content_type.id;


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.django_migrations (
    id integer NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO serveradmin;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.django_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_migrations_id_seq OWNER TO serveradmin;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.django_migrations_id_seq OWNED BY public.django_migrations.id;


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO serveradmin;

--
-- Name: django_site; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.django_site (
    id integer NOT NULL,
    domain character varying(100) NOT NULL,
    name character varying(50) NOT NULL
);


ALTER TABLE public.django_site OWNER TO serveradmin;

--
-- Name: django_site_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.django_site_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_site_id_seq OWNER TO serveradmin;

--
-- Name: django_site_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.django_site_id_seq OWNED BY public.django_site.id;


--
-- Name: graphite_collection; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.graphite_collection (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    params text NOT NULL,
    sort_order double precision NOT NULL,
    overview boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.graphite_collection OWNER TO serveradmin;

--
-- Name: graphite_collection_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.graphite_collection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.graphite_collection_id_seq OWNER TO serveradmin;

--
-- Name: graphite_collection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.graphite_collection_id_seq OWNED BY public.graphite_collection.id;


--
-- Name: graphite_numeric; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.graphite_numeric (
    id integer NOT NULL,
    params text NOT NULL,
    sort_order double precision NOT NULL,
    attribute_id character varying(32) NOT NULL,
    collection_id integer NOT NULL
);


ALTER TABLE public.graphite_numeric OWNER TO serveradmin;

--
-- Name: graphite_numeric_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.graphite_numeric_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.graphite_numeric_id_seq OWNER TO serveradmin;

--
-- Name: graphite_numeric_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.graphite_numeric_id_seq OWNED BY public.graphite_numeric.id;


--
-- Name: graphite_relation; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.graphite_relation (
    id integer NOT NULL,
    sort_order double precision NOT NULL,
    attribute_id character varying(32) NOT NULL,
    collection_id integer NOT NULL
);


ALTER TABLE public.graphite_relation OWNER TO serveradmin;

--
-- Name: graphite_relation_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.graphite_relation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.graphite_relation_id_seq OWNER TO serveradmin;

--
-- Name: graphite_relation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.graphite_relation_id_seq OWNED BY public.graphite_relation.id;


--
-- Name: graphite_template; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.graphite_template (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    params text NOT NULL,
    sort_order double precision NOT NULL,
    description text NOT NULL,
    foreach_path character varying(256) NOT NULL,
    collection_id integer NOT NULL
);


ALTER TABLE public.graphite_template OWNER TO serveradmin;

--
-- Name: graphite_template_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.graphite_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.graphite_template_id_seq OWNER TO serveradmin;

--
-- Name: graphite_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.graphite_template_id_seq OWNED BY public.graphite_template.id;


--
-- Name: graphite_variation; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.graphite_variation (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    params text NOT NULL,
    sort_order double precision NOT NULL,
    summarize_interval character varying(255) NOT NULL,
    collection_id integer NOT NULL
);


ALTER TABLE public.graphite_variation OWNER TO serveradmin;

--
-- Name: graphite_variation_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.graphite_variation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.graphite_variation_id_seq OWNER TO serveradmin;

--
-- Name: graphite_variation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.graphite_variation_id_seq OWNED BY public.graphite_variation.id;


--
-- Name: server; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server (
    server_id integer NOT NULL,
    hostname character varying(254) NOT NULL,
    intern_ip inet,
    servertype_id character varying(32) NOT NULL,
    CONSTRAINT server_hostname_check CHECK (((hostname)::text ~ '\A(\*\.)?([a-z0-9]+(\.|-+))*[a-z0-9]+\Z'::text))
);


ALTER TABLE public.server OWNER TO serveradmin;

--
-- Name: server_boolean_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_boolean_attribute (
    id integer NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_boolean_attribute OWNER TO serveradmin;

--
-- Name: server_boolean_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_boolean_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_boolean_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_boolean_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_boolean_attribute_id_seq OWNED BY public.server_boolean_attribute.id;


--
-- Name: server_date_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_date_attribute (
    id integer NOT NULL,
    value date NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_date_attribute OWNER TO serveradmin;

--
-- Name: server_date_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_date_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_date_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_date_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_date_attribute_id_seq OWNED BY public.server_date_attribute.id;


--
-- Name: server_datetime_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_datetime_attribute (
    id integer NOT NULL,
    value timestamp with time zone NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_datetime_attribute OWNER TO serveradmin;

--
-- Name: server_datetime_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_datetime_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_datetime_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_datetime_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_datetime_attribute_id_seq OWNED BY public.server_datetime_attribute.id;


--
-- Name: server_inet_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_inet_attribute (
    id integer NOT NULL,
    value inet NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_inet_attribute OWNER TO serveradmin;

--
-- Name: server_inet_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_inet_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_inet_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_inet_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_inet_attribute_id_seq OWNED BY public.server_inet_attribute.id;


--
-- Name: server_macaddr_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_macaddr_attribute (
    id integer NOT NULL,
    value macaddr NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_macaddr_attribute OWNER TO serveradmin;

--
-- Name: server_macaddr_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_macaddr_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_macaddr_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_macaddr_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_macaddr_attribute_id_seq OWNED BY public.server_macaddr_attribute.id;


--
-- Name: server_number_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_number_attribute (
    id integer NOT NULL,
    value numeric(65,0) NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL
);


ALTER TABLE public.server_number_attribute OWNER TO serveradmin;

--
-- Name: server_number_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_number_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_number_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_number_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_number_attribute_id_seq OWNED BY public.server_number_attribute.id;


--
-- Name: server_relation_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_relation_attribute (
    id integer NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL,
    value integer NOT NULL
);


ALTER TABLE public.server_relation_attribute OWNER TO serveradmin;

--
-- Name: server_relation_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_relation_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_relation_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_relation_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_relation_attribute_id_seq OWNED BY public.server_relation_attribute.id;


--
-- Name: server_server_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_server_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_server_id_seq OWNER TO serveradmin;

--
-- Name: server_server_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_server_id_seq OWNED BY public.server.server_id;


--
-- Name: server_string_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.server_string_attribute (
    id integer NOT NULL,
    value character varying(1024) NOT NULL,
    attribute_id character varying(32) NOT NULL,
    server_id integer NOT NULL,
    CONSTRAINT server_string_attribute_value_check CHECK (((value)::text <> ''::text))
);


ALTER TABLE public.server_string_attribute OWNER TO serveradmin;

--
-- Name: server_string_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.server_string_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.server_string_attribute_id_seq OWNER TO serveradmin;

--
-- Name: server_string_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.server_string_attribute_id_seq OWNED BY public.server_string_attribute.id;


--
-- Name: serverdb_change; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.serverdb_change (
    id integer NOT NULL,
    change_on timestamp with time zone NOT NULL,
    changes_json text NOT NULL,
    app_id integer,
    user_id integer
);


ALTER TABLE public.serverdb_change OWNER TO serveradmin;

--
-- Name: serverdb_change_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.serverdb_change_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.serverdb_change_id_seq OWNER TO serveradmin;

--
-- Name: serverdb_change_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.serverdb_change_id_seq OWNED BY public.serverdb_change.id;


--
-- Name: serverdb_changeadd; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.serverdb_changeadd (
    id integer NOT NULL,
    server_id integer NOT NULL,
    attributes_json text NOT NULL,
    commit_id integer NOT NULL
);


ALTER TABLE public.serverdb_changeadd OWNER TO serveradmin;

--
-- Name: serverdb_changeadd_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.serverdb_changeadd_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.serverdb_changeadd_id_seq OWNER TO serveradmin;

--
-- Name: serverdb_changeadd_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.serverdb_changeadd_id_seq OWNED BY public.serverdb_changeadd.id;


--
-- Name: serverdb_changecommit; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.serverdb_changecommit (
    id integer NOT NULL,
    change_on timestamp with time zone NOT NULL,
    app_id integer,
    user_id integer
);


ALTER TABLE public.serverdb_changecommit OWNER TO serveradmin;

--
-- Name: serverdb_changecommit_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.serverdb_changecommit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.serverdb_changecommit_id_seq OWNER TO serveradmin;

--
-- Name: serverdb_changecommit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.serverdb_changecommit_id_seq OWNED BY public.serverdb_changecommit.id;


--
-- Name: serverdb_changedelete; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.serverdb_changedelete (
    id integer NOT NULL,
    server_id integer NOT NULL,
    attributes_json text NOT NULL,
    commit_id integer NOT NULL
);


ALTER TABLE public.serverdb_changedelete OWNER TO serveradmin;

--
-- Name: serverdb_changedelete_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.serverdb_changedelete_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.serverdb_changedelete_id_seq OWNER TO serveradmin;

--
-- Name: serverdb_changedelete_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.serverdb_changedelete_id_seq OWNED BY public.serverdb_changedelete.id;


--
-- Name: serverdb_changeupdate; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.serverdb_changeupdate (
    id integer NOT NULL,
    server_id integer NOT NULL,
    updates_json text NOT NULL,
    commit_id integer NOT NULL
);


ALTER TABLE public.serverdb_changeupdate OWNER TO serveradmin;

--
-- Name: serverdb_changeupdate_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.serverdb_changeupdate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.serverdb_changeupdate_id_seq OWNER TO serveradmin;

--
-- Name: serverdb_changeupdate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.serverdb_changeupdate_id_seq OWNED BY public.serverdb_changeupdate.id;


--
-- Name: servertype; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.servertype (
    servertype_id character varying(32) NOT NULL,
    description character varying(1024) NOT NULL,
    ip_addr_type character varying(32) NOT NULL,
    CONSTRAINT servertype_servertype_id_check CHECK (((servertype_id)::text ~ '\A[a-z][a-z0-9_]+\Z'::text))
);


ALTER TABLE public.servertype OWNER TO serveradmin;

--
-- Name: servertype_attribute; Type: TABLE; Schema: public; Owner: serveradmin
--

CREATE TABLE public.servertype_attribute (
    id integer NOT NULL,
    required boolean NOT NULL,
    default_value character varying(255),
    default_visible boolean NOT NULL,
    attribute_id character varying(32) NOT NULL,
    consistent_via_attribute_id character varying(32),
    related_via_attribute_id character varying(32),
    servertype_id character varying(32) NOT NULL,
    CONSTRAINT servertype_attribute_default_value_check CHECK (((default_value)::text <> ''::text))
);


ALTER TABLE public.servertype_attribute OWNER TO serveradmin;

--
-- Name: servertype_attribute_id_seq; Type: SEQUENCE; Schema: public; Owner: serveradmin
--

CREATE SEQUENCE public.servertype_attribute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.servertype_attribute_id_seq OWNER TO serveradmin;

--
-- Name: servertype_attribute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: serveradmin
--

ALTER SEQUENCE public.servertype_attribute_id_seq OWNED BY public.servertype_attribute.id;


--
-- Name: access_control_group id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group ALTER COLUMN id SET DEFAULT nextval('public.access_control_group_id_seq'::regclass);


--
-- Name: access_control_group_applications id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_applications ALTER COLUMN id SET DEFAULT nextval('public.access_control_group_applications_id_seq'::regclass);


--
-- Name: access_control_group_attributes id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_attributes ALTER COLUMN id SET DEFAULT nextval('public.access_control_group_attributes_id_seq'::regclass);


--
-- Name: access_control_group_members id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_members ALTER COLUMN id SET DEFAULT nextval('public.access_control_group_members_id_seq'::regclass);


--
-- Name: api_lock id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.api_lock ALTER COLUMN id SET DEFAULT nextval('public.api_lock_id_seq'::regclass);


--
-- Name: apps_application id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application ALTER COLUMN id SET DEFAULT nextval('public.apps_application_id_seq'::regclass);


--
-- Name: auth_group id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group ALTER COLUMN id SET DEFAULT nextval('public.auth_group_id_seq'::regclass);


--
-- Name: auth_group_permissions id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_group_permissions_id_seq'::regclass);


--
-- Name: auth_permission id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_permission_id_seq'::regclass);


--
-- Name: auth_user id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq'::regclass);


--
-- Name: auth_user_groups id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_groups ALTER COLUMN id SET DEFAULT nextval('public.auth_user_groups_id_seq'::regclass);


--
-- Name: auth_user_user_permissions id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_user_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_user_user_permissions_id_seq'::regclass);


--
-- Name: django_admin_log id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_admin_log ALTER COLUMN id SET DEFAULT nextval('public.django_admin_log_id_seq'::regclass);


--
-- Name: django_content_type id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_content_type ALTER COLUMN id SET DEFAULT nextval('public.django_content_type_id_seq'::regclass);


--
-- Name: django_migrations id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_migrations ALTER COLUMN id SET DEFAULT nextval('public.django_migrations_id_seq'::regclass);


--
-- Name: django_site id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_site ALTER COLUMN id SET DEFAULT nextval('public.django_site_id_seq'::regclass);


--
-- Name: graphite_collection id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_collection ALTER COLUMN id SET DEFAULT nextval('public.graphite_collection_id_seq'::regclass);


--
-- Name: graphite_numeric id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_numeric ALTER COLUMN id SET DEFAULT nextval('public.graphite_numeric_id_seq'::regclass);


--
-- Name: graphite_relation id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_relation ALTER COLUMN id SET DEFAULT nextval('public.graphite_relation_id_seq'::regclass);


--
-- Name: graphite_template id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_template ALTER COLUMN id SET DEFAULT nextval('public.graphite_template_id_seq'::regclass);


--
-- Name: graphite_variation id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_variation ALTER COLUMN id SET DEFAULT nextval('public.graphite_variation_id_seq'::regclass);


--
-- Name: server server_id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server ALTER COLUMN server_id SET DEFAULT nextval('public.server_server_id_seq'::regclass);


--
-- Name: server_boolean_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_boolean_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_boolean_attribute_id_seq'::regclass);


--
-- Name: server_date_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_date_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_date_attribute_id_seq'::regclass);


--
-- Name: server_datetime_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_datetime_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_datetime_attribute_id_seq'::regclass);


--
-- Name: server_inet_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_inet_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_inet_attribute_id_seq'::regclass);


--
-- Name: server_macaddr_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_macaddr_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_macaddr_attribute_id_seq'::regclass);


--
-- Name: server_number_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_number_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_number_attribute_id_seq'::regclass);


--
-- Name: server_relation_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_relation_attribute_id_seq'::regclass);


--
-- Name: server_string_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_string_attribute ALTER COLUMN id SET DEFAULT nextval('public.server_string_attribute_id_seq'::regclass);


--
-- Name: serverdb_change id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_change ALTER COLUMN id SET DEFAULT nextval('public.serverdb_change_id_seq'::regclass);


--
-- Name: serverdb_changeadd id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeadd ALTER COLUMN id SET DEFAULT nextval('public.serverdb_changeadd_id_seq'::regclass);


--
-- Name: serverdb_changecommit id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changecommit ALTER COLUMN id SET DEFAULT nextval('public.serverdb_changecommit_id_seq'::regclass);


--
-- Name: serverdb_changedelete id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changedelete ALTER COLUMN id SET DEFAULT nextval('public.serverdb_changedelete_id_seq'::regclass);


--
-- Name: serverdb_changeupdate id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeupdate ALTER COLUMN id SET DEFAULT nextval('public.serverdb_changeupdate_id_seq'::regclass);


--
-- Name: servertype_attribute id; Type: DEFAULT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute ALTER COLUMN id SET DEFAULT nextval('public.servertype_attribute_id_seq'::regclass);


--
-- Data for Name: access_control_group; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.access_control_group (id, name, query, is_whitelist) FROM stdin;
\.


--
-- Data for Name: access_control_group_applications; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.access_control_group_applications (id, accesscontrolgroup_id, application_id) FROM stdin;
\.


--
-- Data for Name: access_control_group_attributes; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.access_control_group_attributes (id, accesscontrolgroup_id, attribute_id) FROM stdin;
\.


--
-- Data for Name: access_control_group_members; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.access_control_group_members (id, accesscontrolgroup_id, user_id) FROM stdin;
\.


--
-- Data for Name: api_lock; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.api_lock (id, hash_sum, until, duration) FROM stdin;
\.


--
-- Data for Name: apps_application; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.apps_application (id, name, app_id, auth_token, location, disabled, superuser, allowed_methods, owner_id, last_login) FROM stdin;
1	default app for serveradmin	421cbe6b6e6044f785e77267f7f403dd8646be9f	8igR21kG0yspOm9KRwUwozlu		f	t		1	\N
\.


--
-- Data for Name: apps_publickey; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.apps_publickey (key_algorithm, key_base64, key_comment, application_id) FROM stdin;
\.


--
-- Data for Name: attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.attribute (attribute_id, type, multi, hovertext, "group", help_link, readonly, clone, regexp, reversed_attribute_id, target_servertype_id) FROM stdin;
powerdns_domain	relation	f	(Host)Name of the domain this record belongs to.	PowerDNS	\N	f	f	\\A.*\\Z	\N	powerdns_domain
powerdns_domain_type	string	f	PowerDNS domain type	PowerDNS	\N	f	f	\\A(MASTER|SLAVE|NATIVE)\\Z	\N	\N
powerdns_record_aaaa	inet	t	PowerDNS record type AAAA values.	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record_a	inet	t	PowerDNS record type A values.	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record_cname	string	t	PowerDNS record type CNAME values	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record_mx	string	t	PowerDNS record type MX values.	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record_sshfp	string	t	PowerDNS record type SSHFP values.	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record_txt	string	t	PowerDNS record type TXT values.	PowerDNS	\N	f	f	\\A.*\\Z	\N	\N
powerdns_record	relation	t	(Host)Name of the record this mapping belongs to.	PowerDNS	\N	f	f	\\A.*\\Z	\N	powerdns_record
\.


--
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_group (id, name) FROM stdin;
\.


--
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_group_permissions (id, group_id, permission_id) FROM stdin;
\.


--
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_permission (id, name, content_type_id, codename) FROM stdin;
1	Can add log entry	1	add_logentry
2	Can change log entry	1	change_logentry
3	Can delete log entry	1	delete_logentry
4	Can view log entry	1	view_logentry
5	Can add permission	2	add_permission
6	Can change permission	2	change_permission
7	Can delete permission	2	delete_permission
8	Can view permission	2	view_permission
9	Can add group	3	add_group
10	Can change group	3	change_group
11	Can delete group	3	delete_group
12	Can view group	3	view_group
13	Can add user	4	add_user
14	Can change user	4	change_user
15	Can delete user	4	delete_user
16	Can view user	4	view_user
17	Can add content type	5	add_contenttype
18	Can change content type	5	change_contenttype
19	Can delete content type	5	delete_contenttype
20	Can view content type	5	view_contenttype
21	Can add session	6	add_session
22	Can change session	6	change_session
23	Can delete session	6	delete_session
24	Can view session	6	view_session
25	Can add site	7	add_site
26	Can change site	7	change_site
27	Can delete site	7	delete_site
28	Can view site	7	view_site
29	Can add access control group	8	add_accesscontrolgroup
30	Can change access control group	8	change_accesscontrolgroup
31	Can delete access control group	8	delete_accesscontrolgroup
32	Can view access control group	8	view_accesscontrolgroup
33	Can add lock	9	add_lock
34	Can change lock	9	change_lock
35	Can delete lock	9	delete_lock
36	Can view lock	9	view_lock
37	Can add application	10	add_application
38	Can change application	10	change_application
39	Can delete application	10	delete_application
40	Can view application	10	view_application
41	Can add public key	11	add_publickey
42	Can change public key	11	change_publickey
43	Can delete public key	11	delete_publickey
44	Can view public key	11	view_publickey
45	Can add collection	12	add_collection
46	Can change collection	12	change_collection
47	Can delete collection	12	delete_collection
48	Can view collection	12	view_collection
49	Can add numeric	13	add_numeric
50	Can change numeric	13	change_numeric
51	Can delete numeric	13	delete_numeric
52	Can view numeric	13	view_numeric
53	Can add relation	14	add_relation
54	Can change relation	14	change_relation
55	Can delete relation	14	delete_relation
56	Can view relation	14	view_relation
57	Can add template	15	add_template
58	Can change template	15	change_template
59	Can delete template	15	delete_template
60	Can view template	15	view_template
61	Can add variation	16	add_variation
62	Can change variation	16	change_variation
63	Can delete variation	16	delete_variation
64	Can view variation	16	view_variation
65	Can add attribute	17	add_attribute
66	Can change attribute	17	change_attribute
67	Can delete attribute	17	delete_attribute
68	Can view attribute	17	view_attribute
69	Can add change	18	add_change
70	Can change change	18	change_change
71	Can delete change	18	delete_change
72	Can view change	18	view_change
73	Can add change add	19	add_changeadd
74	Can change change add	19	change_changeadd
75	Can delete change add	19	delete_changeadd
76	Can view change add	19	view_changeadd
77	Can add change commit	20	add_changecommit
78	Can change change commit	20	change_changecommit
79	Can delete change commit	20	delete_changecommit
80	Can view change commit	20	view_changecommit
81	Can add change delete	21	add_changedelete
82	Can change change delete	21	change_changedelete
83	Can delete change delete	21	delete_changedelete
84	Can view change delete	21	view_changedelete
85	Can add change update	22	add_changeupdate
86	Can change change update	22	change_changeupdate
87	Can delete change update	22	delete_changeupdate
88	Can view change update	22	view_changeupdate
89	Can add server	23	add_server
90	Can change server	23	change_server
91	Can delete server	23	delete_server
92	Can view server	23	view_server
93	Can add server boolean attribute	24	add_serverbooleanattribute
94	Can change server boolean attribute	24	change_serverbooleanattribute
95	Can delete server boolean attribute	24	delete_serverbooleanattribute
96	Can view server boolean attribute	24	view_serverbooleanattribute
97	Can add server date attribute	25	add_serverdateattribute
98	Can change server date attribute	25	change_serverdateattribute
99	Can delete server date attribute	25	delete_serverdateattribute
100	Can view server date attribute	25	view_serverdateattribute
101	Can add server inet attribute	26	add_serverinetattribute
102	Can change server inet attribute	26	change_serverinetattribute
103	Can delete server inet attribute	26	delete_serverinetattribute
104	Can view server inet attribute	26	view_serverinetattribute
105	Can add server mac address attribute	27	add_servermacaddressattribute
106	Can change server mac address attribute	27	change_servermacaddressattribute
107	Can delete server mac address attribute	27	delete_servermacaddressattribute
108	Can view server mac address attribute	27	view_servermacaddressattribute
109	Can add server number attribute	28	add_servernumberattribute
110	Can change server number attribute	28	change_servernumberattribute
111	Can delete server number attribute	28	delete_servernumberattribute
112	Can view server number attribute	28	view_servernumberattribute
113	Can add server relation attribute	29	add_serverrelationattribute
114	Can change server relation attribute	29	change_serverrelationattribute
115	Can delete server relation attribute	29	delete_serverrelationattribute
116	Can view server relation attribute	29	view_serverrelationattribute
117	Can add server string attribute	30	add_serverstringattribute
118	Can change server string attribute	30	change_serverstringattribute
119	Can delete server string attribute	30	delete_serverstringattribute
120	Can view server string attribute	30	view_serverstringattribute
121	Can add servertype	31	add_servertype
122	Can change servertype	31	change_servertype
123	Can delete servertype	31	delete_servertype
124	Can view servertype	31	view_servertype
125	Can add servertype attribute	32	add_servertypeattribute
126	Can change servertype attribute	32	change_servertypeattribute
127	Can delete servertype attribute	32	delete_servertypeattribute
128	Can view servertype attribute	32	view_servertypeattribute
129	Can add server date time attribute	33	add_serverdatetimeattribute
130	Can change server date time attribute	33	change_serverdatetimeattribute
131	Can delete server date time attribute	33	delete_serverdatetimeattribute
132	Can view server date time attribute	33	view_serverdatetimeattribute
133	Can add domain	34	add_domain
134	Can change domain	34	change_domain
135	Can delete domain	34	delete_domain
136	Can view domain	34	view_domain
137	Can add record	35	add_record
138	Can change record	35	change_record
139	Can delete record	35	delete_record
140	Can view record	35	view_record
\.


--
-- Data for Name: auth_user; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) FROM stdin;
1	pbkdf2_sha256$260000$S8cpRd2tzrJ0ASuK2A5e0T$l8mFdBOJHRK9viRrIU7Ze7mSZl0NridmQ2J0PYpe4NI=	2022-05-17 06:35:28.055568+00	t	serveradmin				t	t	2022-05-17 06:35:13.572801+00
\.


--
-- Data for Name: auth_user_groups; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_user_groups (id, user_id, group_id) FROM stdin;
\.


--
-- Data for Name: auth_user_user_permissions; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.auth_user_user_permissions (id, user_id, permission_id) FROM stdin;
\.


--
-- Data for Name: django_admin_log; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.django_admin_log (id, action_time, object_id, object_repr, action_flag, change_message, content_type_id, user_id) FROM stdin;
1	2022-05-17 07:27:25.320719+00	domain	domain	3		31	1
2	2022-05-17 07:27:25.388206+00	record	record	3		31	1
3	2022-05-17 07:27:31.915892+00	content	content	3		17	1
4	2022-05-17 07:27:31.91997+00	record_type	record_type	3		17	1
5	2022-05-17 07:27:31.921707+00	ttl	ttl	3		17	1
6	2022-05-17 07:27:31.923474+00	type	type	3		17	1
7	2022-05-17 07:28:22.832836+00	powerdns_domain	powerdns_domain	1	[{"added": {}}]	31	1
8	2022-05-17 07:28:51.211721+00	powerdns_record	powerdns_record	1	[{"added": {}}]	31	1
9	2022-05-17 07:30:17.761095+00	powerdns_domain	powerdns_domain	1	[{"added": {}}]	17	1
10	2022-05-17 07:30:34.956898+00	powerdns_record	powerdns_record	2	[{"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_domain"}}]	31	1
11	2022-05-17 07:33:14.685549+00	powerdns_domain_type	powerdns_domain_type	1	[{"added": {}}]	17	1
12	2022-05-17 07:33:36.183346+00	powerdns_domain	powerdns_domain	2	[{"added": {"name": "servertype attribute", "object": "powerdns_domain - powerdns_domain_type"}}]	31	1
13	2022-05-17 07:36:28.061007+00	aaaa	aaaa	1	[{"added": {}}]	17	1
14	2022-05-17 07:36:35.567053+00	aaaa	aaaa	3		17	1
15	2022-05-17 07:37:27.218069+00	powerdns_record_a	powerdns_record_a	1	[{"added": {}}]	17	1
16	2022-05-17 07:37:54.851655+00	powerdns_record_aaaa	powerdns_record_aaaa	1	[{"added": {}}]	17	1
17	2022-05-17 07:38:24.399671+00	powerdns_record_cname	powerdns_record_cname	1	[{"added": {}}]	17	1
18	2022-05-17 07:39:05.772956+00	powerdns_record_txt	powerdns_record_txt	1	[{"added": {}}]	17	1
19	2022-05-17 07:39:16.042256+00	powerdns_record_aaaa	powerdns_record_aaaa	2	[{"changed": {"fields": ["Multi"]}}]	17	1
20	2022-05-17 07:40:02.769861+00	powerdns_record_sshfp	powerdns_record_sshfp	1	[{"added": {}}]	17	1
21	2022-05-17 07:40:33.943339+00	powerdns_record_mx	powerdns_record_mx	1	[{"added": {}}]	17	1
22	2022-05-17 07:48:02.335275+00	powerdns_record	powerdns_record	2	[{"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_record_cname"}}, {"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_record_mx"}}, {"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_record_sshfp"}}, {"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_record_txt"}}]	31	1
23	2022-05-17 07:53:40.032845+00	localbalancer	localbalancer	1	[{"added": {}}]	31	1
24	2022-05-17 07:54:31.191731+00	vm	vm	1	[{"added": {}}]	31	1
25	2022-05-17 07:55:33.82657+00	localbalancer	localbalancer	3		31	1
26	2022-05-17 07:55:44.694069+00	loadbalancer	loadbalancer	1	[{"added": {}}]	31	1
27	2022-05-17 07:57:42.306717+00	vm	vm	2	[{"added": {"name": "servertype attribute", "object": "vm - powerdns_domain"}}]	31	1
28	2022-05-17 07:57:47.0651+00	vm	vm	2	[]	31	1
29	2022-05-17 07:57:51.936241+00	loadbalancer	loadbalancer	2	[{"added": {"name": "servertype attribute", "object": "loadbalancer - powerdns_domain"}}]	31	1
30	2022-05-17 08:00:25.962015+00	powerdns_record	powerdns_record	1	[{"added": {}}]	17	1
31	2022-05-17 08:00:43.948638+00	vm	vm	2	[{"added": {"name": "servertype attribute", "object": "vm - powerdns_record"}}]	31	1
32	2022-05-17 08:00:50.37534+00	loadbalancer	loadbalancer	2	[{"added": {"name": "servertype attribute", "object": "loadbalancer - powerdns_record"}}]	31	1
33	2022-05-17 08:01:24.646347+00	loadbalancer	loadbalancer	2	[{"deleted": {"name": "servertype attribute", "object": "loadbalancer - powerdns_record"}}]	31	1
34	2022-05-17 08:01:29.288594+00	vm	vm	2	[{"deleted": {"name": "servertype attribute", "object": "vm - powerdns_record"}}]	31	1
35	2022-05-17 08:01:39.501894+00	powerdns_record	powerdns_record	3		17	1
36	2022-05-17 08:02:08.578078+00	powerdns_record_a	powerdns_record_a	3		17	1
37	2022-05-17 08:02:13.087703+00	powerdns_record_aaaa	powerdns_record_aaaa	3		17	1
38	2022-05-17 08:04:32.061+00	powerdns_record	powerdns_record	1	[{"added": {}}]	17	1
39	2022-05-17 08:04:47.650048+00	loadbalancer	loadbalancer	2	[{"added": {"name": "servertype attribute", "object": "loadbalancer - powerdns_record"}}]	31	1
40	2022-05-17 08:04:55.894222+00	vm	vm	2	[{"added": {"name": "servertype attribute", "object": "vm - powerdns_record"}}]	31	1
41	2022-05-17 08:05:44.883393+00	powerdns_record_a	powerdns_record_a	1	[{"added": {}}]	17	1
42	2022-05-17 08:05:55.941769+00	powerdns_record	powerdns_record	2	[{"added": {"name": "servertype attribute", "object": "powerdns_record - powerdns_record_a"}}]	31	1
43	2022-05-17 09:45:56.474128+00	powerdns_record_a	powerdns_record_a	3		17	1
44	2022-05-17 09:46:32.334165+00	powerdns_record_a	powerdns_record_a	1	[{"added": {}}]	17	1
45	2022-05-17 09:47:04.556342+00	powerdns_record_aaaa	powerdns_record_aaaa	1	[{"added": {}}]	17	1
46	2022-05-17 09:47:18.232375+00	powerdns_record_a	powerdns_record_a	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
47	2022-05-17 09:47:23.702347+00	powerdns_record_cname	powerdns_record_cname	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
48	2022-05-17 09:47:29.628822+00	powerdns_record_mx	powerdns_record_mx	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
49	2022-05-17 09:47:34.945482+00	powerdns_record_sshfp	powerdns_record_sshfp	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
50	2022-05-17 09:47:40.663727+00	powerdns_record_txt	powerdns_record_txt	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
51	2022-05-17 09:48:01.355664+00	powerdns_record	powerdns_record	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
52	2022-05-17 09:48:46.685533+00	powerdns_record	powerdns_record	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
53	2022-05-17 09:48:56.520812+00	powerdns_record	powerdns_record	2	[{"changed": {"fields": ["Hovertext"]}}]	17	1
\.


--
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.django_content_type (id, app_label, model) FROM stdin;
1	admin	logentry
2	auth	permission
3	auth	group
4	auth	user
5	contenttypes	contenttype
6	sessions	session
7	sites	site
8	access_control	accesscontrolgroup
9	api	lock
10	apps	application
11	apps	publickey
12	graphite	collection
13	graphite	numeric
14	graphite	relation
15	graphite	template
16	graphite	variation
17	serverdb	attribute
18	serverdb	change
19	serverdb	changeadd
20	serverdb	changecommit
21	serverdb	changedelete
22	serverdb	changeupdate
23	serverdb	server
24	serverdb	serverbooleanattribute
25	serverdb	serverdateattribute
26	serverdb	serverinetattribute
27	serverdb	servermacaddressattribute
28	serverdb	servernumberattribute
29	serverdb	serverrelationattribute
30	serverdb	serverstringattribute
31	serverdb	servertype
32	serverdb	servertypeattribute
33	serverdb	serverdatetimeattribute
34	powerdns	domain
35	powerdns	record
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	contenttypes	0001_initial	2022-05-17 06:34:57.845554+00
2	auth	0001_initial	2022-05-17 06:34:57.918879+00
3	apps	0001_initial	2022-05-17 06:34:58.204762+00
4	serverdb	0001_initial	2022-05-17 06:34:58.971276+00
5	access_control	0001_initial	2022-05-17 06:34:59.317345+00
6	access_control	0002_whitelist_blacklist_toggle	2022-05-17 06:34:59.383488+00
7	admin	0001_initial	2022-05-17 06:34:59.416129+00
8	admin	0002_logentry_remove_auto_add	2022-05-17 06:34:59.42916+00
9	admin	0003_logentry_add_action_flag_choices	2022-05-17 06:34:59.441726+00
10	api	0001_api_lock	2022-05-17 06:34:59.452164+00
11	apps	0002_public_key_support	2022-05-17 06:34:59.481763+00
12	apps	0003_public_key_length	2022-05-17 06:34:59.493769+00
13	apps	0004_application_last_login	2022-05-17 06:34:59.507093+00
14	contenttypes	0002_remove_content_type_name	2022-05-17 06:34:59.539501+00
15	auth	0002_alter_permission_name_max_length	2022-05-17 06:34:59.560884+00
16	auth	0003_alter_user_email_max_length	2022-05-17 06:34:59.583112+00
17	auth	0004_alter_user_username_opts	2022-05-17 06:34:59.604316+00
18	auth	0005_alter_user_last_login_null	2022-05-17 06:34:59.626532+00
19	auth	0006_require_contenttypes_0002	2022-05-17 06:34:59.628807+00
20	auth	0007_alter_validators_add_error_messages	2022-05-17 06:34:59.650554+00
21	auth	0008_alter_user_username_max_length	2022-05-17 06:34:59.676628+00
22	auth	0009_alter_user_last_name_max_length	2022-05-17 06:34:59.698207+00
23	auth	0010_alter_group_name_max_length	2022-05-17 06:34:59.721159+00
24	auth	0011_update_proxy_permissions	2022-05-17 06:34:59.74182+00
25	auth	0012_alter_user_first_name_max_length	2022-05-17 06:34:59.764702+00
26	graphite	0001_initial	2022-05-17 06:34:59.992088+00
27	graphite	0002_template_and_variation_name_validation	2022-05-17 06:35:00.003385+00
28	powerdns	0001_initial	2022-05-17 06:35:00.008709+00
29	powerdns	0002_powerdns_schema	2022-05-17 06:35:00.011773+00
30	serverdb	0002_lookup_constraints	2022-05-17 06:35:00.018437+00
31	serverdb	0003_server_indexing	2022-05-17 06:35:00.07827+00
32	serverdb	0004_attribute_value_constraints	2022-05-17 06:35:00.086567+00
33	serverdb	0005_attribute_clone	2022-05-17 06:35:00.09092+00
34	serverdb	0006_datetime_datatype	2022-05-17 06:35:00.18544+00
35	serverdb	0007_hostname_regex_hyphens	2022-05-17 06:35:00.196393+00
36	serverdb	0008_hostname_length_254	2022-05-17 06:35:00.209346+00
37	serverdb	0009_servertype_and_attribute_definitions	2022-05-17 06:35:00.255978+00
38	sessions	0001_initial	2022-05-17 06:35:00.267282+00
39	sites	0001_initial	2022-05-17 06:35:00.273416+00
40	sites	0002_alter_domain_unique	2022-05-17 06:35:00.281149+00
\.


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.django_session (session_key, session_data, expire_date) FROM stdin;
ib3c7lk0xyp44s8pg75ghmb8ikrs279j	.eJxtkNFOwzAMRf8lTyBNJWm7dqvEy3jmCxCK3NilGW1SJemmCvHvuGKgDfESxffeHNv5EBrm1Os5UtAWRSOU2FxrLZh3cquBR3BvPjPepWDbbI1kFzdmzx5pOFyyN4AeYs-vu7yTXYdo9oWSivjAqtrVpt0iQFHmrSpLqqXaF1uuOsJ6RyWgVFVNdbsrGMpMb_w4DZRINCnMdKtpHgEWHQmC4Zb5Vv7rczkCzywadQlEGsgk0XQwRGZGOJGGtG45J4o_rQY72rRiNyJRGHkn6_jitJ0en_hTwDrCw3KXg5RN86Cqe5459v7sbmAvovcxORiJ7V_CGqVwopCWaTUmf6aALupAxge8VtCP3Er_DX7L4vXzCxFbomg:1nt6Jr:euR414nBWtWH6bUvwtcFCaY0EwRXRvIRkPaxpGz_XTI	2022-06-06 11:33:51.251431+00
\.


--
-- Data for Name: django_site; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.django_site (id, domain, name) FROM stdin;
1	example.com	example.com
\.


--
-- Data for Name: graphite_collection; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.graphite_collection (id, name, params, sort_order, overview, created_at) FROM stdin;
\.


--
-- Data for Name: graphite_numeric; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.graphite_numeric (id, params, sort_order, attribute_id, collection_id) FROM stdin;
\.


--
-- Data for Name: graphite_relation; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.graphite_relation (id, sort_order, attribute_id, collection_id) FROM stdin;
\.


--
-- Data for Name: graphite_template; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.graphite_template (id, name, params, sort_order, description, foreach_path, collection_id) FROM stdin;
\.


--
-- Data for Name: graphite_variation; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.graphite_variation (id, name, params, sort_order, summarize_interval, collection_id) FROM stdin;
\.


--
-- Data for Name: server; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server (server_id, hostname, intern_ip, servertype_id) FROM stdin;
7	sunrisevillage.de	\N	powerdns_domain
8	de1.sunrisevillage.de	\N	powerdns_record
9	host-1.ig.local	10.0.0.1	vm
10	hostlb.innogames.net	212.48.98.12	loadbalancer
11	ig.local	\N	powerdns_domain
12	innogames.net	\N	powerdns_domain
13	*.sunrisevillage.de	\N	powerdns_record
14	hostlb2.innogames.net	212.32.32.10	loadbalancer
\.


--
-- Data for Name: server_boolean_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_boolean_attribute (id, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_date_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_date_attribute (id, value, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_datetime_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_datetime_attribute (id, value, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_inet_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_inet_attribute (id, value, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_macaddr_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_macaddr_attribute (id, value, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_number_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_number_attribute (id, value, attribute_id, server_id) FROM stdin;
\.


--
-- Data for Name: server_relation_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_relation_attribute (id, attribute_id, server_id, value) FROM stdin;
4	powerdns_domain	8	7
5	powerdns_domain	9	11
6	powerdns_domain	10	12
7	powerdns_record	10	8
8	powerdns_domain	13	7
9	powerdns_record	10	13
10	powerdns_record	14	8
\.


--
-- Data for Name: server_string_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.server_string_attribute (id, value, attribute_id, server_id) FROM stdin;
8	NATIVE	powerdns_domain_type	7
9	foo	powerdns_record_txt	8
10	NATIVE	powerdns_domain_type	11
11	NATIVE	powerdns_domain_type	12
13	10 a	powerdns_record_mx	13
14	20 b	powerdns_record_mx	13
15	30 c	powerdns_record_mx	13
\.


--
-- Data for Name: serverdb_change; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.serverdb_change (id, change_on, changes_json, app_id, user_id) FROM stdin;
\.


--
-- Data for Name: serverdb_changeadd; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.serverdb_changeadd (id, server_id, attributes_json, commit_id) FROM stdin;
1	1	{"object_id": 1, "hostname": "ig.local", "intern_ip": null, "servertype": "domain", "type": "NATIVE"}	1
2	2	{"object_id": 2, "hostname": "ns1", "intern_ip": null, "servertype": "record", "content": "localhost", "domain": "ig.local", "record_type": "NS", "ttl": 300}	2
3	3	{"object_id": 3, "hostname": "soa", "intern_ip": null, "servertype": "record", "content": "localhost hostmaster.ig.local", "domain": "ig.local", "record_type": "SOA", "ttl": 300}	3
4	5	{"object_id": 5, "hostname": "host.ig.local", "intern_ip": null, "servertype": "record", "content": "bingo", "domain": "ig.local", "record_type": "TXT", "ttl": 300}	5
5	7	{"object_id": 7, "hostname": "sunrisevillage.de", "intern_ip": null, "servertype": "powerdns_domain", "powerdns_domain_type": "NATIVE"}	9
6	8	{"object_id": 8, "hostname": "de1.sunrisevillage.de", "intern_ip": null, "servertype": "powerdns_record", "powerdns_domain": "sunrisevillage.de", "powerdns_record_cname": [], "powerdns_record_mx": [], "powerdns_record_sshfp": [], "powerdns_record_txt": ["foo"]}	10
7	9	{"object_id": 9, "hostname": "host-1.ig.local", "intern_ip": "10.0.0.1", "servertype": "vm"}	11
8	10	{"object_id": 10, "hostname": "hostlb.innogames.net", "intern_ip": "212.48.98.12", "servertype": "loadbalancer"}	12
9	11	{"object_id": 11, "hostname": "ig.local", "intern_ip": null, "servertype": "powerdns_domain", "powerdns_domain_type": "NATIVE"}	13
10	12	{"object_id": 12, "hostname": "innogames.net", "intern_ip": null, "servertype": "powerdns_domain", "powerdns_domain_type": "NATIVE"}	14
11	13	{"object_id": 13, "hostname": "*.sunrisevillage.de", "intern_ip": null, "servertype": "powerdns_record", "powerdns_domain": "sunrisevillage.de", "powerdns_record_a": null, "powerdns_record_cname": [], "powerdns_record_mx": ["lololol"], "powerdns_record_sshfp": [], "powerdns_record_txt": []}	17
12	14	{"object_id": 14, "hostname": "hostlb2.innogames.net", "intern_ip": "212.32.32.10", "servertype": "loadbalancer", "powerdns_domain": null, "powerdns_record": []}	20
\.


--
-- Data for Name: serverdb_changecommit; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.serverdb_changecommit (id, change_on, app_id, user_id) FROM stdin;
1	2022-05-17 06:37:14.641181+00	\N	1
2	2022-05-17 06:37:56.046079+00	\N	1
3	2022-05-17 06:40:04.022441+00	\N	1
5	2022-05-17 06:43:01.063153+00	\N	1
8	2022-05-17 07:27:17.050319+00	\N	1
9	2022-05-17 07:48:30.383152+00	\N	1
10	2022-05-17 07:51:51.747652+00	\N	1
11	2022-05-17 07:55:09.042663+00	\N	1
12	2022-05-17 07:56:11.468567+00	\N	1
13	2022-05-17 07:56:56.495335+00	\N	1
14	2022-05-17 07:57:07.869845+00	\N	1
15	2022-05-17 07:58:06.909091+00	\N	1
16	2022-05-17 08:06:39.892294+00	\N	1
17	2022-05-17 08:09:19.949481+00	\N	1
18	2022-05-17 08:09:42.724251+00	\N	1
19	2022-05-19 14:29:51.731899+00	\N	1
20	2022-05-19 14:40:23.74718+00	\N	1
21	2022-05-19 14:41:02.421843+00	\N	1
\.


--
-- Data for Name: serverdb_changedelete; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.serverdb_changedelete (id, server_id, attributes_json, commit_id) FROM stdin;
1	1	{"object_id": 1, "hostname": "ig.local", "intern_ip": null, "servertype": "domain", "type": "NATIVE"}	8
2	2	{"object_id": 2, "hostname": "ns1", "intern_ip": null, "servertype": "record", "content": "localhost", "domain": "ig.local", "record_type": "NS", "ttl": 300}	8
3	3	{"object_id": 3, "hostname": "soa", "intern_ip": null, "servertype": "record", "content": "localhost hostmaster.ig.local", "domain": "ig.local", "record_type": "SOA", "ttl": 300}	8
4	5	{"object_id": 5, "hostname": "host.ig.local", "intern_ip": null, "servertype": "record", "content": "bingo", "domain": "ig.local", "record_type": "TXT", "ttl": 300}	8
\.


--
-- Data for Name: serverdb_changeupdate; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.serverdb_changeupdate (id, server_id, updates_json, commit_id) FROM stdin;
1	9	{"powerdns_domain": {"action": "update", "new": "ig.local", "old": null}, "object_id": 9}	15
2	10	{"powerdns_domain": {"action": "update", "new": "innogames.net", "old": null}, "object_id": 10}	15
3	10	{"powerdns_record": {"action": "multi", "add": ["de1.sunrisevillage.de"], "remove": []}, "object_id": 10}	16
4	10	{"powerdns_record": {"action": "multi", "add": ["*.sunrisevillage.de"], "remove": []}, "object_id": 10}	18
5	13	{"powerdns_record_mx": {"action": "multi", "add": ["10 a", "20 b", "30 c"], "remove": ["lololol"]}, "object_id": 13}	19
6	14	{"powerdns_record": {"action": "multi", "add": ["de1.sunrisevillage.de"], "remove": []}, "object_id": 14}	21
\.


--
-- Data for Name: servertype; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.servertype (servertype_id, description, ip_addr_type) FROM stdin;
powerdns_domain	PowerDNS Domain	null
loadbalancer	LB-Pool	loadbalancer
vm	Linux Kernel-based Virtual Machine	host
powerdns_record	PowerDNS Record	null
\.


--
-- Data for Name: servertype_attribute; Type: TABLE DATA; Schema: public; Owner: serveradmin
--

COPY public.servertype_attribute (id, required, default_value, default_visible, attribute_id, consistent_via_attribute_id, related_via_attribute_id, servertype_id) FROM stdin;
7	t	\N	f	powerdns_domain	\N	\N	powerdns_record
8	t	NATIVE	f	powerdns_domain_type	\N	\N	powerdns_domain
9	f	\N	f	powerdns_record_cname	\N	\N	powerdns_record
10	f	\N	f	powerdns_record_mx	\N	\N	powerdns_record
11	f	\N	f	powerdns_record_sshfp	\N	\N	powerdns_record
12	f	\N	f	powerdns_record_txt	\N	\N	powerdns_record
13	f	\N	f	powerdns_domain	\N	\N	vm
14	f	\N	f	powerdns_domain	\N	\N	loadbalancer
17	f	\N	f	powerdns_record	\N	\N	loadbalancer
18	f	\N	f	powerdns_record	\N	\N	vm
\.


--
-- Name: access_control_group_applications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.access_control_group_applications_id_seq', 1, false);


--
-- Name: access_control_group_attributes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.access_control_group_attributes_id_seq', 1, false);


--
-- Name: access_control_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.access_control_group_id_seq', 1, false);


--
-- Name: access_control_group_members_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.access_control_group_members_id_seq', 1, false);


--
-- Name: api_lock_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.api_lock_id_seq', 1, false);


--
-- Name: apps_application_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.apps_application_id_seq', 1, true);


--
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_group_id_seq', 1, false);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_group_permissions_id_seq', 1, false);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_permission_id_seq', 140, true);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_user_groups_id_seq', 1, false);


--
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_user_id_seq', 1, true);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.auth_user_user_permissions_id_seq', 1, false);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.django_admin_log_id_seq', 53, true);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.django_content_type_id_seq', 35, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 40, true);


--
-- Name: django_site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.django_site_id_seq', 1, true);


--
-- Name: graphite_collection_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.graphite_collection_id_seq', 1, false);


--
-- Name: graphite_numeric_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.graphite_numeric_id_seq', 1, false);


--
-- Name: graphite_relation_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.graphite_relation_id_seq', 1, false);


--
-- Name: graphite_template_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.graphite_template_id_seq', 1, false);


--
-- Name: graphite_variation_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.graphite_variation_id_seq', 1, false);


--
-- Name: server_boolean_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_boolean_attribute_id_seq', 1, false);


--
-- Name: server_date_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_date_attribute_id_seq', 1, false);


--
-- Name: server_datetime_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_datetime_attribute_id_seq', 1, false);


--
-- Name: server_inet_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_inet_attribute_id_seq', 1, false);


--
-- Name: server_macaddr_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_macaddr_attribute_id_seq', 1, false);


--
-- Name: server_number_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_number_attribute_id_seq', 3, true);


--
-- Name: server_relation_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_relation_attribute_id_seq', 10, true);


--
-- Name: server_server_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_server_id_seq', 14, true);


--
-- Name: server_string_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.server_string_attribute_id_seq', 15, true);


--
-- Name: serverdb_change_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.serverdb_change_id_seq', 1, false);


--
-- Name: serverdb_changeadd_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.serverdb_changeadd_id_seq', 12, true);


--
-- Name: serverdb_changecommit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.serverdb_changecommit_id_seq', 21, true);


--
-- Name: serverdb_changedelete_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.serverdb_changedelete_id_seq', 4, true);


--
-- Name: serverdb_changeupdate_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.serverdb_changeupdate_id_seq', 6, true);


--
-- Name: servertype_attribute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: serveradmin
--

SELECT pg_catalog.setval('public.servertype_attribute_id_seq', 19, true);


--
-- Name: access_control_group_applications access_control_group_app_accesscontrolgroup_id_ap_ad625f80_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_applications
    ADD CONSTRAINT access_control_group_app_accesscontrolgroup_id_ap_ad625f80_uniq UNIQUE (accesscontrolgroup_id, application_id);


--
-- Name: access_control_group_applications access_control_group_applications_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_applications
    ADD CONSTRAINT access_control_group_applications_pkey PRIMARY KEY (id);


--
-- Name: access_control_group_attributes access_control_group_att_accesscontrolgroup_id_at_5c9b3a4c_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_attributes
    ADD CONSTRAINT access_control_group_att_accesscontrolgroup_id_at_5c9b3a4c_uniq UNIQUE (accesscontrolgroup_id, attribute_id);


--
-- Name: access_control_group_attributes access_control_group_attributes_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_attributes
    ADD CONSTRAINT access_control_group_attributes_pkey PRIMARY KEY (id);


--
-- Name: access_control_group_members access_control_group_mem_accesscontrolgroup_id_us_3acba33e_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_members
    ADD CONSTRAINT access_control_group_mem_accesscontrolgroup_id_us_3acba33e_uniq UNIQUE (accesscontrolgroup_id, user_id);


--
-- Name: access_control_group_members access_control_group_members_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_members
    ADD CONSTRAINT access_control_group_members_pkey PRIMARY KEY (id);


--
-- Name: access_control_group access_control_group_name_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group
    ADD CONSTRAINT access_control_group_name_key UNIQUE (name);


--
-- Name: access_control_group access_control_group_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group
    ADD CONSTRAINT access_control_group_pkey PRIMARY KEY (id);


--
-- Name: api_lock api_lock_hash_sum_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.api_lock
    ADD CONSTRAINT api_lock_hash_sum_key UNIQUE (hash_sum);


--
-- Name: api_lock api_lock_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.api_lock
    ADD CONSTRAINT api_lock_pkey PRIMARY KEY (id);


--
-- Name: apps_application apps_application_app_id_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application
    ADD CONSTRAINT apps_application_app_id_key UNIQUE (app_id);


--
-- Name: apps_application apps_application_auth_token_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application
    ADD CONSTRAINT apps_application_auth_token_key UNIQUE (auth_token);


--
-- Name: apps_application apps_application_name_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application
    ADD CONSTRAINT apps_application_name_key UNIQUE (name);


--
-- Name: apps_application apps_application_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application
    ADD CONSTRAINT apps_application_pkey PRIMARY KEY (id);


--
-- Name: apps_publickey apps_publickey_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_publickey
    ADD CONSTRAINT apps_publickey_pkey PRIMARY KEY (key_base64);


--
-- Name: attribute attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.attribute
    ADD CONSTRAINT attribute_pkey PRIMARY KEY (attribute_id);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: django_site django_site_domain_a2e37b91_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_site
    ADD CONSTRAINT django_site_domain_a2e37b91_uniq UNIQUE (domain);


--
-- Name: django_site django_site_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_site
    ADD CONSTRAINT django_site_pkey PRIMARY KEY (id);


--
-- Name: graphite_collection graphite_collection_name_overview_a8093ed9_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_collection
    ADD CONSTRAINT graphite_collection_name_overview_a8093ed9_uniq UNIQUE (name, overview);


--
-- Name: graphite_collection graphite_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_collection
    ADD CONSTRAINT graphite_collection_pkey PRIMARY KEY (id);


--
-- Name: graphite_numeric graphite_numeric_collection_id_attribute_id_602e9b10_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_numeric
    ADD CONSTRAINT graphite_numeric_collection_id_attribute_id_602e9b10_uniq UNIQUE (collection_id, attribute_id);


--
-- Name: graphite_numeric graphite_numeric_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_numeric
    ADD CONSTRAINT graphite_numeric_pkey PRIMARY KEY (id);


--
-- Name: graphite_relation graphite_relation_collection_id_attribute_id_cd8f6803_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_relation
    ADD CONSTRAINT graphite_relation_collection_id_attribute_id_cd8f6803_uniq UNIQUE (collection_id, attribute_id);


--
-- Name: graphite_relation graphite_relation_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_relation
    ADD CONSTRAINT graphite_relation_pkey PRIMARY KEY (id);


--
-- Name: graphite_template graphite_template_collection_id_name_d94c6b17_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_template
    ADD CONSTRAINT graphite_template_collection_id_name_d94c6b17_uniq UNIQUE (collection_id, name);


--
-- Name: graphite_template graphite_template_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_template
    ADD CONSTRAINT graphite_template_pkey PRIMARY KEY (id);


--
-- Name: graphite_variation graphite_variation_collection_id_name_9ba36e62_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_variation
    ADD CONSTRAINT graphite_variation_collection_id_name_9ba36e62_uniq UNIQUE (collection_id, name);


--
-- Name: graphite_variation graphite_variation_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_variation
    ADD CONSTRAINT graphite_variation_pkey PRIMARY KEY (id);


--
-- Name: server_boolean_attribute server_boolean_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_boolean_attribute
    ADD CONSTRAINT server_boolean_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_boolean_attribute server_boolean_attribute_server_id_attribute_id_6bbd8242_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_boolean_attribute
    ADD CONSTRAINT server_boolean_attribute_server_id_attribute_id_6bbd8242_uniq UNIQUE (server_id, attribute_id);


--
-- Name: server_date_attribute server_date_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_date_attribute
    ADD CONSTRAINT server_date_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_date_attribute server_date_attribute_server_id_attribute_id_v_6dbed874_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_date_attribute
    ADD CONSTRAINT server_date_attribute_server_id_attribute_id_v_6dbed874_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server_datetime_attribute server_datetime_attribut_server_id_attribute_id_v_01f2547b_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_datetime_attribute
    ADD CONSTRAINT server_datetime_attribut_server_id_attribute_id_v_01f2547b_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server_datetime_attribute server_datetime_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_datetime_attribute
    ADD CONSTRAINT server_datetime_attribute_pkey PRIMARY KEY (id);


--
-- Name: server server_hostname_key; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server
    ADD CONSTRAINT server_hostname_key UNIQUE (hostname);


--
-- Name: server_inet_attribute server_inet_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_inet_attribute
    ADD CONSTRAINT server_inet_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_inet_attribute server_inet_attribute_server_id_attribute_id_v_99a96b34_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_inet_attribute
    ADD CONSTRAINT server_inet_attribute_server_id_attribute_id_v_99a96b34_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server server_inter_ip_exclude; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server
    ADD CONSTRAINT server_inter_ip_exclude EXCLUDE USING gist (intern_ip inet_ops WITH &&, servertype_id WITH =) WHERE (((servertype_id)::text <> 'loadbalancer'::text));


--
-- Name: server_macaddr_attribute server_macaddr_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_macaddr_attribute
    ADD CONSTRAINT server_macaddr_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_macaddr_attribute server_macaddr_attribute_server_id_attribute_id_v_1f33a2ee_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_macaddr_attribute
    ADD CONSTRAINT server_macaddr_attribute_server_id_attribute_id_v_1f33a2ee_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server_number_attribute server_number_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_number_attribute
    ADD CONSTRAINT server_number_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_number_attribute server_number_attribute_server_id_attribute_id_v_ddd40781_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_number_attribute
    ADD CONSTRAINT server_number_attribute_server_id_attribute_id_v_ddd40781_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server server_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server
    ADD CONSTRAINT server_pkey PRIMARY KEY (server_id);


--
-- Name: server_relation_attribute server_relation_attribut_server_id_attribute_id_v_ab4d9995_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute
    ADD CONSTRAINT server_relation_attribut_server_id_attribute_id_v_ab4d9995_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: server_relation_attribute server_relation_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute
    ADD CONSTRAINT server_relation_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_string_attribute server_string_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_string_attribute
    ADD CONSTRAINT server_string_attribute_pkey PRIMARY KEY (id);


--
-- Name: server_string_attribute server_string_attribute_server_id_attribute_id_v_690ce414_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_string_attribute
    ADD CONSTRAINT server_string_attribute_server_id_attribute_id_v_690ce414_uniq UNIQUE (server_id, attribute_id, value);


--
-- Name: serverdb_change serverdb_change_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_change
    ADD CONSTRAINT serverdb_change_pkey PRIMARY KEY (id);


--
-- Name: serverdb_changeadd serverdb_changeadd_commit_id_server_id_faff3d42_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeadd
    ADD CONSTRAINT serverdb_changeadd_commit_id_server_id_faff3d42_uniq UNIQUE (commit_id, server_id);


--
-- Name: serverdb_changeadd serverdb_changeadd_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeadd
    ADD CONSTRAINT serverdb_changeadd_pkey PRIMARY KEY (id);


--
-- Name: serverdb_changecommit serverdb_changecommit_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changecommit
    ADD CONSTRAINT serverdb_changecommit_pkey PRIMARY KEY (id);


--
-- Name: serverdb_changedelete serverdb_changedelete_commit_id_server_id_1c635883_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changedelete
    ADD CONSTRAINT serverdb_changedelete_commit_id_server_id_1c635883_uniq UNIQUE (commit_id, server_id);


--
-- Name: serverdb_changedelete serverdb_changedelete_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changedelete
    ADD CONSTRAINT serverdb_changedelete_pkey PRIMARY KEY (id);


--
-- Name: serverdb_changeupdate serverdb_changeupdate_commit_id_server_id_28f207ac_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeupdate
    ADD CONSTRAINT serverdb_changeupdate_commit_id_server_id_28f207ac_uniq UNIQUE (commit_id, server_id);


--
-- Name: serverdb_changeupdate serverdb_changeupdate_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeupdate
    ADD CONSTRAINT serverdb_changeupdate_pkey PRIMARY KEY (id);


--
-- Name: servertype_attribute servertype_attribute_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_pkey PRIMARY KEY (id);


--
-- Name: servertype_attribute servertype_attribute_servertype_id_attribute_id_eb89174e_uniq; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_servertype_id_attribute_id_eb89174e_uniq UNIQUE (servertype_id, attribute_id);


--
-- Name: servertype servertype_pkey; Type: CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype
    ADD CONSTRAINT servertype_pkey PRIMARY KEY (servertype_id);


--
-- Name: access_control_group_appli_accesscontrolgroup_id_fc0d0a71; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_appli_accesscontrolgroup_id_fc0d0a71 ON public.access_control_group_applications USING btree (accesscontrolgroup_id);


--
-- Name: access_control_group_applications_application_id_c9303431; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_applications_application_id_c9303431 ON public.access_control_group_applications USING btree (application_id);


--
-- Name: access_control_group_attributes_accesscontrolgroup_id_5ee69ddd; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_attributes_accesscontrolgroup_id_5ee69ddd ON public.access_control_group_attributes USING btree (accesscontrolgroup_id);


--
-- Name: access_control_group_attributes_attribute_id_90fae58c; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_attributes_attribute_id_90fae58c ON public.access_control_group_attributes USING btree (attribute_id);


--
-- Name: access_control_group_attributes_attribute_id_90fae58c_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_attributes_attribute_id_90fae58c_like ON public.access_control_group_attributes USING btree (attribute_id varchar_pattern_ops);


--
-- Name: access_control_group_members_accesscontrolgroup_id_c540d0de; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_members_accesscontrolgroup_id_c540d0de ON public.access_control_group_members USING btree (accesscontrolgroup_id);


--
-- Name: access_control_group_members_user_id_121f20f4; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_members_user_id_121f20f4 ON public.access_control_group_members USING btree (user_id);


--
-- Name: access_control_group_name_d458b0e4_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX access_control_group_name_d458b0e4_like ON public.access_control_group USING btree (name varchar_pattern_ops);


--
-- Name: api_lock_hash_sum_bff8800e_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX api_lock_hash_sum_bff8800e_like ON public.api_lock USING btree (hash_sum varchar_pattern_ops);


--
-- Name: apps_application_app_id_b598654e_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_application_app_id_b598654e_like ON public.apps_application USING btree (app_id varchar_pattern_ops);


--
-- Name: apps_application_auth_token_89f63725_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_application_auth_token_89f63725_like ON public.apps_application USING btree (auth_token varchar_pattern_ops);


--
-- Name: apps_application_name_d7571844_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_application_name_d7571844_like ON public.apps_application USING btree (name varchar_pattern_ops);


--
-- Name: apps_application_owner_id_0baec2b3; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_application_owner_id_0baec2b3 ON public.apps_application USING btree (owner_id);


--
-- Name: apps_publickey_application_id_52eb9110; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_publickey_application_id_52eb9110 ON public.apps_publickey USING btree (application_id);


--
-- Name: apps_publickey_key_base64_35f0def6_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX apps_publickey_key_base64_35f0def6_like ON public.apps_publickey USING btree (key_base64 varchar_pattern_ops);


--
-- Name: attribute_attribute_id_7d9244d0_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX attribute_attribute_id_7d9244d0_like ON public.attribute USING btree (attribute_id varchar_pattern_ops);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: django_site_domain_a2e37b91_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX django_site_domain_a2e37b91_like ON public.django_site USING btree (domain varchar_pattern_ops);


--
-- Name: graphite_numeric_attribute_id_88244c59; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_numeric_attribute_id_88244c59 ON public.graphite_numeric USING btree (attribute_id);


--
-- Name: graphite_numeric_attribute_id_88244c59_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_numeric_attribute_id_88244c59_like ON public.graphite_numeric USING btree (attribute_id varchar_pattern_ops);


--
-- Name: graphite_numeric_collection_id_df34a1f3; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_numeric_collection_id_df34a1f3 ON public.graphite_numeric USING btree (collection_id);


--
-- Name: graphite_relation_attribute_id_2f352462; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_relation_attribute_id_2f352462 ON public.graphite_relation USING btree (attribute_id);


--
-- Name: graphite_relation_attribute_id_2f352462_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_relation_attribute_id_2f352462_like ON public.graphite_relation USING btree (attribute_id varchar_pattern_ops);


--
-- Name: graphite_relation_collection_id_7d3b0dcb; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_relation_collection_id_7d3b0dcb ON public.graphite_relation USING btree (collection_id);


--
-- Name: graphite_template_collection_id_96835e82; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_template_collection_id_96835e82 ON public.graphite_template USING btree (collection_id);


--
-- Name: graphite_variation_collection_id_bb3f8a11; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX graphite_variation_collection_id_bb3f8a11 ON public.graphite_variation USING btree (collection_id);


--
-- Name: server_boolean_attribute_attribute_id_b1ad575f; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_boolean_attribute_attribute_id_b1ad575f ON public.server_boolean_attribute USING btree (attribute_id);


--
-- Name: server_boolean_attribute_attribute_id_b1ad575f_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_boolean_attribute_attribute_id_b1ad575f_idx ON public.server_boolean_attribute USING btree (attribute_id);


--
-- Name: server_boolean_attribute_attribute_id_b1ad575f_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_boolean_attribute_attribute_id_b1ad575f_like ON public.server_boolean_attribute USING btree (attribute_id varchar_pattern_ops);


--
-- Name: server_date_attribute_attribute_id_value_92c2e130_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_date_attribute_attribute_id_value_92c2e130_idx ON public.server_date_attribute USING btree (attribute_id, value);


--
-- Name: server_datetime_attribute_attribute_id_value_0dde96d5_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_datetime_attribute_attribute_id_value_0dde96d5_idx ON public.server_datetime_attribute USING btree (attribute_id, value);


--
-- Name: server_hostname_b385a781_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_hostname_b385a781_like ON public.server USING btree (hostname varchar_pattern_ops);


--
-- Name: server_hostname_trgm; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_hostname_trgm ON public.server USING gin (hostname public.gin_trgm_ops);


--
-- Name: server_inet_attribute_attribute_id_value_5fb6797b_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_inet_attribute_attribute_id_value_5fb6797b_idx ON public.server_inet_attribute USING btree (attribute_id, value);


--
-- Name: server_macaddr_attribute_attribute_id_value_49d23836_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_macaddr_attribute_attribute_id_value_49d23836_idx ON public.server_macaddr_attribute USING btree (attribute_id, value);


--
-- Name: server_number_attribute_attribute_id_value_0b02c803_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_number_attribute_attribute_id_value_0b02c803_idx ON public.server_number_attribute USING btree (attribute_id, value);


--
-- Name: server_relation_attribute_attribute_id_value_5c4dfd1c_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_relation_attribute_attribute_id_value_5c4dfd1c_idx ON public.server_relation_attribute USING btree (attribute_id, value);


--
-- Name: server_servertype_id_7a1f440f; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_servertype_id_7a1f440f ON public.server USING btree (servertype_id);


--
-- Name: server_servertype_id_7a1f440f_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_servertype_id_7a1f440f_like ON public.server USING btree (servertype_id varchar_pattern_ops);


--
-- Name: server_string_attribute_attribute_id_value_d6e99d79_idx; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX server_string_attribute_attribute_id_value_d6e99d79_idx ON public.server_string_attribute USING btree (attribute_id, value);


--
-- Name: serverdb_change_app_id_1b798c85; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_change_app_id_1b798c85 ON public.serverdb_change USING btree (app_id);


--
-- Name: serverdb_change_change_on_7ad85427; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_change_change_on_7ad85427 ON public.serverdb_change USING btree (change_on);


--
-- Name: serverdb_change_user_id_0e8cce5b; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_change_user_id_0e8cce5b ON public.serverdb_change USING btree (user_id);


--
-- Name: serverdb_changeadd_commit_id_b6661243; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changeadd_commit_id_b6661243 ON public.serverdb_changeadd USING btree (commit_id);


--
-- Name: serverdb_changeadd_server_id_6b6c8c19; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changeadd_server_id_6b6c8c19 ON public.serverdb_changeadd USING btree (server_id);


--
-- Name: serverdb_changecommit_app_id_73cb4baf; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changecommit_app_id_73cb4baf ON public.serverdb_changecommit USING btree (app_id);


--
-- Name: serverdb_changecommit_change_on_4ea3b2a0; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changecommit_change_on_4ea3b2a0 ON public.serverdb_changecommit USING btree (change_on);


--
-- Name: serverdb_changecommit_user_id_4822c638; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changecommit_user_id_4822c638 ON public.serverdb_changecommit USING btree (user_id);


--
-- Name: serverdb_changedelete_commit_id_ed67b6f2; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changedelete_commit_id_ed67b6f2 ON public.serverdb_changedelete USING btree (commit_id);


--
-- Name: serverdb_changedelete_server_id_1ab30147; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changedelete_server_id_1ab30147 ON public.serverdb_changedelete USING btree (server_id);


--
-- Name: serverdb_changeupdate_commit_id_691c30ca; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changeupdate_commit_id_691c30ca ON public.serverdb_changeupdate USING btree (commit_id);


--
-- Name: serverdb_changeupdate_server_id_31332993; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX serverdb_changeupdate_server_id_31332993 ON public.serverdb_changeupdate USING btree (server_id);


--
-- Name: servertype_servertype_id_95831609_like; Type: INDEX; Schema: public; Owner: serveradmin
--

CREATE INDEX servertype_servertype_id_95831609_like ON public.servertype USING btree (servertype_id varchar_pattern_ops);


--
-- Name: access_control_group_attributes access_control_group_accesscontrolgroup_i_5ee69ddd_fk_access_co; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_attributes
    ADD CONSTRAINT access_control_group_accesscontrolgroup_i_5ee69ddd_fk_access_co FOREIGN KEY (accesscontrolgroup_id) REFERENCES public.access_control_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: access_control_group_members access_control_group_accesscontrolgroup_i_c540d0de_fk_access_co; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_members
    ADD CONSTRAINT access_control_group_accesscontrolgroup_i_c540d0de_fk_access_co FOREIGN KEY (accesscontrolgroup_id) REFERENCES public.access_control_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: access_control_group_applications access_control_group_accesscontrolgroup_i_fc0d0a71_fk_access_co; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_applications
    ADD CONSTRAINT access_control_group_accesscontrolgroup_i_fc0d0a71_fk_access_co FOREIGN KEY (accesscontrolgroup_id) REFERENCES public.access_control_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: access_control_group_applications access_control_group_application_id_c9303431_fk_apps_appl; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_applications
    ADD CONSTRAINT access_control_group_application_id_c9303431_fk_apps_appl FOREIGN KEY (application_id) REFERENCES public.apps_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: access_control_group_attributes access_control_group_attribute_id_90fae58c_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_attributes
    ADD CONSTRAINT access_control_group_attribute_id_90fae58c_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: access_control_group_members access_control_group_members_user_id_121f20f4_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.access_control_group_members
    ADD CONSTRAINT access_control_group_members_user_id_121f20f4_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: apps_application apps_application_owner_id_0baec2b3_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_application
    ADD CONSTRAINT apps_application_owner_id_0baec2b3_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: apps_publickey apps_publickey_application_id_52eb9110_fk_apps_application_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.apps_publickey
    ADD CONSTRAINT apps_publickey_application_id_52eb9110_fk_apps_application_id FOREIGN KEY (application_id) REFERENCES public.apps_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: attribute attribute_reversed_attribute_i_0dfb83ac_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.attribute
    ADD CONSTRAINT attribute_reversed_attribute_i_0dfb83ac_fk_attribute FOREIGN KEY (reversed_attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: attribute attribute_target_servertype_id_0eab2dcc_fk_servertyp; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.attribute
    ADD CONSTRAINT attribute_target_servertype_id_0eab2dcc_fk_servertyp FOREIGN KEY (target_servertype_id) REFERENCES public.servertype(servertype_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_numeric graphite_numeric_attribute_id_88244c59_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_numeric
    ADD CONSTRAINT graphite_numeric_attribute_id_88244c59_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_numeric graphite_numeric_collection_id_df34a1f3_fk_graphite_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_numeric
    ADD CONSTRAINT graphite_numeric_collection_id_df34a1f3_fk_graphite_ FOREIGN KEY (collection_id) REFERENCES public.graphite_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_relation graphite_relation_attribute_id_2f352462_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_relation
    ADD CONSTRAINT graphite_relation_attribute_id_2f352462_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_relation graphite_relation_collection_id_7d3b0dcb_fk_graphite_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_relation
    ADD CONSTRAINT graphite_relation_collection_id_7d3b0dcb_fk_graphite_ FOREIGN KEY (collection_id) REFERENCES public.graphite_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_template graphite_template_collection_id_96835e82_fk_graphite_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_template
    ADD CONSTRAINT graphite_template_collection_id_96835e82_fk_graphite_ FOREIGN KEY (collection_id) REFERENCES public.graphite_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graphite_variation graphite_variation_collection_id_bb3f8a11_fk_graphite_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.graphite_variation
    ADD CONSTRAINT graphite_variation_collection_id_bb3f8a11_fk_graphite_ FOREIGN KEY (collection_id) REFERENCES public.graphite_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_boolean_attribute server_boolean_attri_attribute_id_b1ad575f_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_boolean_attribute
    ADD CONSTRAINT server_boolean_attri_attribute_id_b1ad575f_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_boolean_attribute server_boolean_attribute_server_id_f298dd92_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_boolean_attribute
    ADD CONSTRAINT server_boolean_attribute_server_id_f298dd92_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_date_attribute server_date_attribut_attribute_id_da524b5f_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_date_attribute
    ADD CONSTRAINT server_date_attribut_attribute_id_da524b5f_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_date_attribute server_date_attribute_server_id_6b0a5f23_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_date_attribute
    ADD CONSTRAINT server_date_attribute_server_id_6b0a5f23_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_datetime_attribute server_datetime_attr_attribute_id_267c546f_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_datetime_attribute
    ADD CONSTRAINT server_datetime_attr_attribute_id_267c546f_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_datetime_attribute server_datetime_attr_server_id_7e99ffa9_fk_server_se; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_datetime_attribute
    ADD CONSTRAINT server_datetime_attr_server_id_7e99ffa9_fk_server_se FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_inet_attribute server_inet_attribut_attribute_id_d3ffd83b_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_inet_attribute
    ADD CONSTRAINT server_inet_attribut_attribute_id_d3ffd83b_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_inet_attribute server_inet_attribute_server_id_971d8988_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_inet_attribute
    ADD CONSTRAINT server_inet_attribute_server_id_971d8988_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_macaddr_attribute server_macaddr_attri_attribute_id_3592cef5_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_macaddr_attribute
    ADD CONSTRAINT server_macaddr_attri_attribute_id_3592cef5_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_macaddr_attribute server_macaddr_attribute_server_id_e76c6ad1_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_macaddr_attribute
    ADD CONSTRAINT server_macaddr_attribute_server_id_e76c6ad1_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_number_attribute server_number_attrib_attribute_id_a7c8738c_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_number_attribute
    ADD CONSTRAINT server_number_attrib_attribute_id_a7c8738c_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_number_attribute server_number_attribute_server_id_0131ae8e_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_number_attribute
    ADD CONSTRAINT server_number_attribute_server_id_0131ae8e_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_relation_attribute server_relation_attr_attribute_id_f971ac6d_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute
    ADD CONSTRAINT server_relation_attr_attribute_id_f971ac6d_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_relation_attribute server_relation_attr_server_id_7367ee06_fk_server_se; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute
    ADD CONSTRAINT server_relation_attr_server_id_7367ee06_fk_server_se FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_relation_attribute server_relation_attribute_value_563c1ba4_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_relation_attribute
    ADD CONSTRAINT server_relation_attribute_value_563c1ba4_fk_server_server_id FOREIGN KEY (value) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server server_servertype_id_7a1f440f_fk_servertype_servertype_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server
    ADD CONSTRAINT server_servertype_id_7a1f440f_fk_servertype_servertype_id FOREIGN KEY (servertype_id) REFERENCES public.servertype(servertype_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_string_attribute server_string_attrib_attribute_id_8116442b_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_string_attribute
    ADD CONSTRAINT server_string_attrib_attribute_id_8116442b_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: server_string_attribute server_string_attribute_server_id_a126825b_fk_server_server_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.server_string_attribute
    ADD CONSTRAINT server_string_attribute_server_id_a126825b_fk_server_server_id FOREIGN KEY (server_id) REFERENCES public.server(server_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_change serverdb_change_app_id_1b798c85_fk_apps_application_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_change
    ADD CONSTRAINT serverdb_change_app_id_1b798c85_fk_apps_application_id FOREIGN KEY (app_id) REFERENCES public.apps_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_change serverdb_change_user_id_0e8cce5b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_change
    ADD CONSTRAINT serverdb_change_user_id_0e8cce5b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_changeadd serverdb_changeadd_commit_id_b6661243_fk_serverdb_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeadd
    ADD CONSTRAINT serverdb_changeadd_commit_id_b6661243_fk_serverdb_ FOREIGN KEY (commit_id) REFERENCES public.serverdb_changecommit(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_changecommit serverdb_changecommit_app_id_73cb4baf_fk_apps_application_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changecommit
    ADD CONSTRAINT serverdb_changecommit_app_id_73cb4baf_fk_apps_application_id FOREIGN KEY (app_id) REFERENCES public.apps_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_changecommit serverdb_changecommit_user_id_4822c638_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changecommit
    ADD CONSTRAINT serverdb_changecommit_user_id_4822c638_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_changedelete serverdb_changedelet_commit_id_ed67b6f2_fk_serverdb_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changedelete
    ADD CONSTRAINT serverdb_changedelet_commit_id_ed67b6f2_fk_serverdb_ FOREIGN KEY (commit_id) REFERENCES public.serverdb_changecommit(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: serverdb_changeupdate serverdb_changeupdat_commit_id_691c30ca_fk_serverdb_; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.serverdb_changeupdate
    ADD CONSTRAINT serverdb_changeupdat_commit_id_691c30ca_fk_serverdb_ FOREIGN KEY (commit_id) REFERENCES public.serverdb_changecommit(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: servertype_attribute servertype_attribute_attribute_id_7178d5a3_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_attribute_id_7178d5a3_fk_attribute FOREIGN KEY (attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: servertype_attribute servertype_attribute_consistent_via_attri_7de73045_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_consistent_via_attri_7de73045_fk_attribute FOREIGN KEY (consistent_via_attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: servertype_attribute servertype_attribute_related_via_attribut_09fcc314_fk_attribute; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_related_via_attribut_09fcc314_fk_attribute FOREIGN KEY (related_via_attribute_id) REFERENCES public.attribute(attribute_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: servertype_attribute servertype_attribute_servertype_id_861fa7c8_fk_servertyp; Type: FK CONSTRAINT; Schema: public; Owner: serveradmin
--

ALTER TABLE ONLY public.servertype_attribute
    ADD CONSTRAINT servertype_attribute_servertype_id_861fa7c8_fk_servertyp FOREIGN KEY (servertype_id) REFERENCES public.servertype(servertype_id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

