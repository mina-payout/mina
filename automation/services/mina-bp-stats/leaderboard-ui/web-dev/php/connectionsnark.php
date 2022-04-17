<?php

$username = getenv("DB_SNARK_USER");
$password = getenv("DB_SNARK_PWD");
$database_name = getenv("DB_SNARK_DB");
$port = getenv("DB_SNARK_PORT");
$host = getenv("DB_SNARK_HOST");
$conn = pg_connect("host=".$host." port=".$port." dbname=".$database_name." user=".$username." password=".$password."") or die("Connection failed: " .pg_last_error());

return $conn

?>