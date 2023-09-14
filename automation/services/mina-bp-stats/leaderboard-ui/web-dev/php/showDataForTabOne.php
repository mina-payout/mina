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
if (! (isset($_POST['perPageCount']))) {
    $perPageCount = 10;
} else {
    $perPageCount = $_POST['perPageCount'];
}
// $perPageCount = 10;

$rowCount = (int)$tabledata['rowCount'] ;
//echo $rowCount;
$maxScore = (int)$tabledata['maxScore'] ;
$last_modified = $tabledata['last_modified'] ;

//echo $maxScore;
$pagesCount = ceil($rowCount / $perPageCount);
$lowerLimit = ($pageNumber - 1) * $perPageCount;
$pagestart = $_POST['pagestart'] ?? null;
$rowData = $tabledata['row'];
if($SearchInputData != null){
    $newArray = array();
    foreach ($rowData as $key => $rowDataKey){
        if(stripos((strtolower($rowDataKey['block_producer_key'])),$SearchInputData) !== false) {
            //array_push($newArray, $rowDataKey);
            $rowDataKey['index'] = $key + 1;
            $newArray[$key] = $rowDataKey;
        }
    }
    $rowData = $newArray ;
    $rowCount = count($newArray);
    //$maxScore =count($newArray);
    $pagesCount = ceil($rowCount / $perPageCount);
}
$row = array_slice($rowData,$pagestart,$perPageCount);
$counter = $lowerLimit + 1;

// $console = 'console.log(' . json_encode($SearchInputData) . ');';
// echo $console;
?>
<div class="container mb-0 mt-0 performance-Container">

<div class="selectNav">
    <p class="selectNav_perpage_title mr13px">Results Per Page</p>
    <select class="selectNav_selector mr13px" value="<?php echo $perPageCount ?>" onchange="showDataForTabOne(this.value, '<?php  echo 1;  ?>', '<?php  echo 0;  ?>');">
       <?php for ($x = 10; $x <= 100; $x+=10) { ?>
          <option value="<?php echo $x ?>" <?php if($perPageCount==$x)echo 'selected' ?> ><?php echo $x ?></option>
       <?php } ?>
    </select>
    <ul class="selectNav_list">
    
    <li >
        <a class="<?php if($pageNumber > 1) {echo 'page-active ';} else {echo 'page-disable';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php if($pageNumber <= 1){ echo $pageNumber; } else { echo ($pageNumber - 1); } ?>', '<?php  echo ($lowerLimit - $perPageCount);  ?>');">Prev</a></li>
    </li>
    <li >
      <a class="<?php if($pageNumber <= 1) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo 1;  ?>', '<?php  echo 0;  ?>');">1</a>
    </li>
    <li >
      <a class="<?php if($pageNumber ==2 ) {echo 'page-disable';} else {echo 'page-active';}?>"href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo 2;  ?>', '<?php  echo 0;  ?>');">2</a>
    </li>
    <li>.
        <?php
         if($pageNumber>2 && ($pageNumber <($pagesCount-1))) { ?>
      <a class="page-disable" href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pageNumber;  ?>', '<?php  echo 0;  ?>');"> <?php echo $pageNumber ?> </a>
            
        <?php } else echo '.' ?>
        
    .</li>
    
    <li >
      <a class="<?php if($pageNumber == $pagesCount-1) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pagesCount-1;  ?>', '<?php  echo (($pagesCount - 2) * $perPageCount) ;  ?>');"><?php echo $pagesCount-1?></a>
    </li>
    <li >
      <a class="<?php if($pageNumber == $pagesCount) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pagesCount;  ?>', '<?php  echo (($pagesCount - 1) * $perPageCount) ;  ?>');"><?php echo $pagesCount ?></a>
    </li>
    <li >
        <a class="<?php if($pageNumber == $pagesCount) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php if($pageNumber >= $pagesCount){ echo $pageNumber; } else { echo ($pageNumber + 1); } ?>', '<?php  echo ($lowerLimit + $perPageCount);  ?>');">Next</a>
    </li>
    <!-- <li class = "mr-3 mt-1 p-2 d-none d-md-block">Page <?php echo $pageNumber; ?> of <?php echo $pagesCount; ?></li> -->
  </ul>

  <span class="list_last_update d-sm-block  ">Last updated <?php echo $last_modified ?></span>

</div>
</div>


<div class="container pr-0 pl-0 mt-0 mb-5 tab-content">
        <div class="table-responsive table-responsive-sm table-responsive-md table-responsive-lg table-responsive-xl tab-pane fade show active" id="Data-table" role="tabpanel" aria-labelledby="Data-table">
            <table class="table table-striped text-center">
                <thead>
                    <tr class="border-top-0">
                        <th scope="col">RANK</th>
                        <th scope="col" class="text-left">PUBLIC KEY</th>
                        <?php 
                        if($ShowScoreColumn == true){
                        ?>
                        <th scope="col">SCORE(90-Day)</th>
                        <?php }?>
                        <th scope="col">%(Max Score <?php echo $maxScore ?>) </th>
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
                        <td scope="row"><?php if($SearchInputData != null) {echo $data['index'];}else{echo $counter;} ?></td>
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

        <div class="container mb-0 mt-0 performance-Container">

<div class="selectNav" style="position:relative" >
    <p class="selectNav_perpage_title mr13px">Results Per Page</p>
    <select class="selectNav_selector mr13px" value="<?php echo $perPageCount ?>" onchange="showDataForTabOne(this.value, '<?php  echo 1;  ?>', '<?php  echo 0;  ?>');">
       <?php for ($x = 10; $x <= 100; $x+=10) { ?>
          <option value="<?php echo $x ?>" <?php if($perPageCount==$x)echo 'selected' ?> ><?php echo $x ?></option>
       <?php } ?>
    </select>
    <ul class="selectNav_list">
    
    <li >
        <a class="<?php if($pageNumber > 1) {echo 'page-active ';} else {echo 'page-disable';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php if($pageNumber <= 1){ echo $pageNumber; } else { echo ($pageNumber - 1); } ?>', '<?php  echo ($lowerLimit - $perPageCount);  ?>');">Prev</a></li>

    </li>
    


    <li >
      <a class="<?php if($pageNumber <= 1) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo 1;  ?>', '<?php  echo 0;  ?>');">1</a>
    </li>
    <li >
      <a class="<?php if($pageNumber ==2 ) {echo 'page-disable';} else {echo 'page-active';}?>"href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo 2;  ?>', '<?php  echo 0;  ?>');">2</a>
    </li>
    <li>.
        <?php
         if($pageNumber>2 && ($pageNumber <($pagesCount-1))) { ?>
      <a class="page-disable" href="javascript:void(0);" tabindex="-1" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pageNumber;  ?>', '<?php  echo 0;  ?>');"> <?php echo $pageNumber ?> </a>
            
        <?php } else echo '.' ?>
        
    .</li>
    
    <li >
      <a class="<?php if($pageNumber == $pagesCount-1) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pagesCount-1;  ?>', '<?php  echo (($pagesCount - 2) * $perPageCount) ;  ?>');"><?php echo $pagesCount-1?></a>
    </li>
    <li >
      <a class="<?php if($pageNumber == $pagesCount) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php  echo $pagesCount;  ?>', '<?php  echo (($pagesCount - 1) * $perPageCount) ;  ?>');"><?php echo $pagesCount ?></a>
    </li>
    <li >
        <a class="<?php if($pageNumber == $pagesCount) {echo 'page-disable';} else {echo 'page-active';}?>" href="javascript:void(0);" onclick="showDataForTabOne('<?php echo $perPageCount;  ?>', '<?php if($pageNumber >= $pagesCount){ echo $pageNumber; } else { echo ($pageNumber + 1); } ?>', '<?php  echo ($lowerLimit + $perPageCount);  ?>');">Next</a>
    </li>
    <!-- <li class = "mr-3 mt-1 p-2 d-none d-md-block">Page <?php echo $pageNumber; ?> of <?php echo $pagesCount; ?></li> -->
  </ul>


</div>
</div>

    </div>
    
    <div style="height: 30px;"></div>



