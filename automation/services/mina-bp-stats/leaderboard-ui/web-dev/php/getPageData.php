<?php
require_once ("connection.php");


if (! (isset($_GET['pageNumber']))) {
    $pageNumber = 1;
} else {
    $pageNumber = $_GET['pageNumber'];
}

$perPageCount = 120;

$sql = "SELECT COUNT(*) FROM nodes WHERE application_status = true and score is not null";


if ($result = pg_query($conn, $sql)) {
    $row = pg_fetch_row($result);
    $rowCount = $row[0];
    pg_free_result($result);
}

$pagesCount = ceil($rowCount / $perPageCount);

$lowerLimit = ($pageNumber - 1) * $perPageCount;


$sqlQuery = "SELECT block_producer_key , score ,score_percent FROM nodes WHERE application_status = true and score is not null ORDER BY score DESC";

    $results = pg_query($conn, $sqlQuery);
    $row = pg_fetch_all($results);
    
      
    echo json_encode(array('row' => $row, 'rowCount' => $rowCount));

?>
    