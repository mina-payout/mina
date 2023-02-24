<?php
require_once ("connectionsnark.php");

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



$maxScoreSnark= " WITH recentone as ( 
		SELECT batch_end_epoch end_epoch, extract('epoch' FROM (to_timestamp(batch_end_epoch) - interval '90' day )) start_epoch 
	    FROM bot_logs b 
	    where file_timestamps <= CURRENT_TIMESTAMP 
	    ORDER BY batch_end_epoch DESC LIMIT 1
    ) 
    SELECT COUNT(1),  to_char(to_timestamp(end_epoch),  'DD-MM-YYYY hh24:mi') as last_modified
    FROM bot_logs , recentone
    WHERE batch_start_epoch >=  start_epoch and batch_end_epoch <= end_epoch
    group by 2     ";

     
    $maxScoreSnarkresult = pg_query($conn, $maxScoreSnark);
    $maxScoreRow = pg_fetch_row($maxScoreSnarkresult);
    $maxScore = $maxScoreRow[0];
    $last_modified=$maxScoreRow[1];

    echo json_encode(array('row' => $row, 'rowCount' => $rowCount, 'maxScore' => $maxScore, 'last_modified'=>$last_modified));

?>
