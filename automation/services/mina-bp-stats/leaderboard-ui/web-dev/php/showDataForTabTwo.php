<?php

$myarray = include 'config.php';

$ShowScoreColumn = $myarray[0];
$MaintenanceMode = $myarray[2];


$tabledata = json_decode($_POST['tabledata'], true) ;
$SearchInputData = $_POST['search_input'];
   
if (! (isset($_POST['pageNumber']))) {
    $pageNumber = 1;
} else {
    $pageNumber = $_POST['pageNumber'];
}

$perPageCount = 120;

$rowCount = (int)$tabledata['rowCount'] ;

$pagesCount = ceil($rowCount / $perPageCount);
$lowerLimit = ($pageNumber - 1) * $perPageCount;
$pagestart = $_POST['pagestart'] ?? null;
$rowData = $tabledata['row'];

if($SearchInputData != null){
    $newArray = array();
    foreach ($rowData as $key => $rowDataKey){
        if(stripos((strtolower($rowDataKey['block_producer_key'])),$SearchInputData) !== false) {
            array_push($newArray, $rowDataKey);
        }
    }
    $rowData = $newArray ;
    $rowCount = count($newArray);
    $pagesCount = ceil($rowCount / $perPageCount);
}

$row = array_slice($rowData,$pagestart,$perPageCount);
$counter = $lowerLimit + 1;
?>
<div class="container mb-0 mt-0 performance-Container">
<div class="row mx-1 d-flex justify-content-end">
<div class="d-flex flex-row-reverse mb-2 mx-sm-auto mx-lg-0">
<nav aria-label="Page navigation example" style="<?php if($MaintenanceMode == true) {echo 'display: none;';}?>">
  <ul class="pagination justify-content-center">
    <li class="<?php if($pageNumber <= 1) {echo 'page-item disabled';} else {echo 'page-item';}?>">
      <a class="page-link" href="javascript:void(0);" tabindex="-1" onclick="showDataForTabTwo('<?php echo $perPageCount;  ?>', '<?php  echo 1;  ?>', '<?php  echo 0;  ?>');">First</a>
    </li>
    <li class="<?php if($pageNumber <= 1) {echo 'page-item disabled';} else {echo 'page-item';}?>">
        <a class="page-link" href="javascript:void(0);" onclick="showDataForTabTwo('<?php echo $perPageCount;  ?>', '<?php if($pageNumber <= 1){ echo $pageNumber; } else { echo ($pageNumber - 1); } ?>', '<?php  echo ($counter - 1);  ?>');">Prev</a></li>
    <li class="<?php if($pageNumber == $pagesCount) {echo 'page-item disabled';} else {echo 'page-item';}?>">
        <a class="page-link" href="javascript:void(0);" onclick="showDataForTabTwo('<?php echo $perPageCount;  ?>', '<?php if($pageNumber >= $pagesCount){ echo $pageNumber; } else { echo ($pageNumber + 1); } ?>', '<?php  echo ($counter - 1);  ?>');">Next</a></li>
    <li class="<?php if($pageNumber == $pagesCount) {echo 'page-item disabled';} else {echo 'page-item';}?>">
      <a class="page-link" href="javascript:void(0);" onclick="showDataForTabTwo('<?php echo $perPageCount;  ?>', '<?php  echo $pagesCount;  ?>', '<?php  echo (($pagesCount - 1) * $perPageCount) ;  ?>');">Last</a>
    </li>
    <li class = "mr-3 mt-1 p-2 d-none d-md-block">Page <?php echo $pageNumber; ?> of <?php echo $pagesCount; ?></li>
  </ul>
</nav>
</div>
<span class="d-block  d-md-none">Page <?php echo $pageNumber; ?> of <?php echo $pagesCount; ?></span>
</div>
</div>

<div class="container pr-0 pl-0 mt-1 mb-5 tab-content">
        <div class="table-responsive table-responsive-sm table-responsive-md table-responsive-lg table-responsive-xl tab-pane fade show active" id="Data-table-2" role="tabpanel" aria-labelledby="Data-table-2">
            <table class="table table-striped text-center">
                <thead>
                    <tr class="border-top-0">
                        <th scope="col">RANK</th>
                        <th scope="col" class="text-left">PUBLIC KEY</th>
                        <?php 
                        if($ShowScoreColumn == true){
                        ?>
                        <th scope="col">SCORE(60 Day)</th>
                        <?php }?>
                        <th scope="col">SCORE PERCENT</th>
                    </tr>
                </thead>
                <tbody class="">
                <tr style="<?php if($MaintenanceMode != true) {echo 'display: none;';}?>">
                    <td colspan ="<?php if($ShowScoreColumn != true) {echo '3';} else {echo '4';}?>">
                        <div class="wrap">
                            <i class="bi bi-exclamation-triangle-fill" style="font-size: 5rem; color: #b0afaf;"></i>
                            <h1 class="maintenanceText">Under Maintenance</h1>
                        </div>
                    </td>
                </tr>
                <?php 

                 if($MaintenanceMode != true){
                foreach ($row as $key => $data) { 
                   
                    ?>
                    
                    <tr>
                        <td scope="row"><?php echo $counter ?></td>
                        <td><?php echo $data['block_producer_key'] ?></td>
                        <?php 
                        if($ShowScoreColumn == true){
                        ?>
                        <td><?php echo $data['score'] ?></td>
                        <?php }?>
                        <td><?php echo $data['score_percent'] ?> %</td>
                    </tr>
                    <?php
                     $counter++;
    }
}
    ?>
                </tbody>
            </table>
        </div>
        <div id="apiLink" class="d-flex flex-row-reverse">
        <i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i><a class="Mina-Refrance-color " href="/apidocs" target="_blank">MINA Open API for Uptime Data</a>
        </div>
    </div>
    <div style="height: 30px;"></div>



