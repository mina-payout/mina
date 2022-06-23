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
 
$maxScoreSidecar= "WITH recentone as (SELECT batch_end_epoch end_epoch , extract('epoch' FROM (to_timestamp(batch_end_epoch) - interval '60' day )) start_epoch
    FROM bot_logs b WHERE file_timestamps <= CURRENT_TIMESTAMP ORDER BY batch_end_epoch DESC LIMIT 1) 
    SELECT COUNT(1) FROM bot_logs , recentone WHERE batch_start_epoch BETWEEN start_epoch and end_epoch";

        
    $maxScoreSidecarresult = pg_query($conn, $maxScoreSidecar);
    $maxScoreRow = pg_fetch_row($maxScoreSidecarresult); 
    $SidecarmaxScore = $maxScoreRow[0];
    
    
      
    echo json_encode(array('row' => $row, 'rowCount' => $rowCount, 'SidecarmaxScore' => $SidecarmaxScore));



?>
    