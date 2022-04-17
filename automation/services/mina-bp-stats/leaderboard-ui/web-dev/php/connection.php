

<?php

$username = getenv("DB_SIDECAR_USER");
$password = getenv("DB_SIDECAR_PWD");
$database_name = getenv("DB_SIDECAR_DB");
$port = getenv("DB_SIDECAR_PORT");
$host = getenv("DB_SIDECAR_HOST");
$conn = pg_connect("host=".$host." port=".$port." dbname=".$database_name." user=".$username." password=".$password."") or die("Connection failed: " .pg_last_error());

return $conn

?>