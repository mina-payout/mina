

<?php

$username = "";
$password = "";
$database_name = "";
$port = "";
$host = "";
$conn = pg_connect("host=".$host." port=".$port." dbname=".$database_name." user=".$username." password=".$password."") or die("Connection failed: " .pg_last_error());

return $conn

?>