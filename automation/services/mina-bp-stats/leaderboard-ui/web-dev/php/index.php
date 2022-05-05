<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Uptime Leaderboard</title>

    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
    <script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.4.0/font/bootstrap-icons.css">

    <link rel="stylesheet" href="assets/css/custome.css">
    <link rel="stylesheet" href="assets/css/responsive.css">

    <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.3/jquery.min.js"></script>
</head>

<body>
    <div class="mina-banner">
        <div class="bannerFlex">
            <div class="bannerAnnouncement"> Find the list of delegated block producers
            <a class="Mina-Refrance-color" href="<?php $myarray = include 'config.php'; $Configurl =  $myarray[1];  echo $Configurl;  ?>" target="_blank">here</a>
            </div>
        </div>
    </div>
    <div class="container">

        <!-- Logo And Header Section Start -->
        <div class="row mb-3 minalogo">
               <img src="assets/images/MinaWordmark.png" alt="Mina" class="mina-main-logo d-block mx-auto mx-md-0">
        </div>
        <div class="row mb-5 mina-subheader-text">
            <div class="subheader">
                <p class="mina-subheader-text-font">Block Producers Uptime Tracker </p>
            </div>
        </div>
        <!-- Logo And Header Section End -->

        <!-- Top Button and Link Section Start -->
        <div class="row mb-3">
            <div class="uptime-lederboard-topButton"></div>
            <div class="col-12 col-md-6 mx-0 px-0 topButton">
                <button type="button" class="delegationButton btn btn-dark btn-primary" onclick="window.open('https://docs.google.com/forms/d/e/1FAIpQLSduM5EIpwZtf5ohkVepKzs3q0v0--FDEaDfbP2VD4V6GcBepA/viewform')">APPLY FOR DELEGATION <i class="bi bi-arrow-right "></i>
                </button>
                <div class="bottomPlate for-normal" id="leaderBoardbtn">
                </div>
            </div>
            <div class="col-12 col-md-6 mx-0 px-0 Link-responcive">
                <div class="d-flex flex-row-reverse mb-2">
                    <div class="flex-column d-none d-sm-block">
                    <div class="text-right"><a class="Mina-Refrance-color alignment-link" href="https://forums.minaprotocol.com/t/delegation-program-faq/4246" target="_blank">FAQ</a><i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i></div>
                    <div class="text-right"><a class="Mina-Refrance-color alignment-link" href="https://minaprotocol.com/blog/mina-foundation-delegation-policy" target="_blank">Mina Foundation Delegation Policy</a><i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i></div>
                    </div>
                </div>
                <!-- for mobile view -->
                <div class="d-flex flex-row">
                    <div class="d-flex d-sm-none">
                        <div class="p-1"><a class="Mina-Refrance-color alignment-link" href="https://forums.minaprotocol.com/t/delegation-program-faq/4246" target="_blank">FAQ</a><i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i></div>
                        <div class="p-1"><a class="Mina-Refrance-color alignment-link" href="https://minaprotocol.com/blog/mina-foundation-delegation-policy" target="_blank">Mina Foundation Delegation Policy</a><i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i></div>
                    </div>
                </div>
                <!-- <div class="row Link-responcive"> -->

                    <!-- <a class="Mina-Refrance-color ml-auto alignment-link" href="https://medium.com/o1labs/o-1-labs-delegation-policy-786bf96f9fdd" target="_blank">O(1) Labs Delegation Policy</a><i class="ml-2 bi bi-box-arrow-up-right Mina-Refrance-color"></i> -->
                <!-- </div> -->
            </div>
        </div>
        <!-- Top Button and Link Section End -->
        <div class="row mb-4">
            <div class="">
                <p>Ranking for the Mina Foundation Uptime Leaderboard are based on data from the Sidecar Uptime System.</p>
            </div>
        </div>
           <!-- Tab and Search Section Start -->
    <div class="container mb-3 mt-0 mx-sm-0 performance-Container">
        <div class="responcive-tab">
            <div class="row mx-1">
                <div class="col-12 px-0 mx-0">
                    <!-- <div class="row">
                        <label for="View" class="text-uppercase">VIEW</label>
                    </div> -->
                    <div class="row Mobile-Tab-view">
                    <ul class="nav nav-pills text-uppercase text-center">
                            <li class="nav-item left-box">

                                <a data-toggle="pill" class="nav-link active " href="#Data-table" aria-controls="Data-table" aria-selected="true" id="table-one" onclick='showDataForTabOne (10, 1, 0)'>
                                <div class="beta-text">
                                SIDECAR UPTIME SYSTEM (Current)
                                </div>

                            </a>
                            </li>
                            <li class="nav-item right-box">

                                <a data-toggle="pill" class="nav-link" href="#Data-table-2" aria-controls="Data-table-2" aria-selected="false" id="table-two" onclick='showDataForTabTwo (10, 1, 0)'>
                                <div class="beta-text">
                                SNARK-WORK UPTIME SYSTEM (Beta)
                                </div>
                            </a>
                            </li>
                        </ul>
                        <div class="bottom-plate-tab"></div>
                    </div>
                </div>
                <div class="col-12 col-sm-12 col-md-12 col-lg-12 col-xl-6  px-0 mx-0 ">

                    <div class="row">
                        <input type="search" class="form-control mb-2 mt-2 search-box" id="search-input" placeholder="Search Public Key" onkeyup="search_result()">
                    </div>
                </div>
            </div>
        </div>

    </div>
    <!-- Tab and Search Section End -->
    </div>



    <!-- Data Table Section Start -->
    <div id="result"></div>
    <div id="result2"></div>

    <div id="loaderSpin"></div>


    <!-- Data Table Section End -->



    <script type="text/javascript">
   var tabledata ;
   var tabledataSnark ;
    function getRecords(perPageCount, pageNumber ) {

        $.ajax({
            type: "GET",
            url: "getPageData.php",
            data: {pageNumber: pageNumber},

            cache: false,
    		beforeSend: function() {
                $('#loaderSpin').html('<div class="spinner-border d-flex mx-auto" role="status"><span class="sr-only">Loading...</span></div>');

            },
            success: function(response) {
                 tabledata = response;
                 $("ul li a").each(function () {
                    if ($('#table-one').attr("aria-controls") === "Data-table" && $('#table-one').attr("aria-selected") === "true") {
                        showDataForTabOne (10, 1, 0);
            }
            // else if ($('#table-two').attr("aria-controls") === "Data-table-2" && $('#table-two').attr("aria-selected") === "true") {
            //             alert("hello tab 2");
            //             showDataForTabTwo (10, 1, 0);
            // }
        });
                $('#loaderSpin').html('');
            },

        });
    }

    function getRecordsForSnark(perPageCount, pageNumber ) {

    $.ajax({
        type: "GET",
        url: "getPageDataForSnark.php",
        data: {pageNumber: pageNumber},

        cache: false,
        beforeSend: function() {
            $('#loaderSpin').html('<div class="spinner-border d-flex mx-auto" role="status"><span class="sr-only">Loading...</span></div>');

        },
        success: function(response) {
            // alert(response);
            tabledataSnark = response;
             $("ul li a").each(function () {
                 if ($('#table-two').attr("aria-controls") === "Data-table-2" && $('#table-two').attr("aria-selected") === "true") {
                    showDataForTabTwo (10, 1, 0);
        }
    });
            $('#loaderSpin').html('');
        },

    });
}

    function showDataForTabOne(perPageCount, pageNumber, pagestart , input ) {
       if(!input){input = null}
    $.ajax({
        type: "POST",
        url: "showDataForTabOne.php",
        data: {pageNumber: pageNumber ,pagestart:pagestart, tabledata : tabledata , search_input : input},

        cache: false,
        success: function(html) {
            $('#loaderSpin').html('');
            $("#result2").html('');
            $("#result").html(html);
        },

    });
}

function showDataForTabTwo(perPageCount, pageNumber, pagestart ,input ) {
    if(!input){input = null}
       $.ajax({
           type: "POST",
           url: "showDataForTabTwo.php",
           data: {pageNumber: pageNumber ,pagestart:pagestart, tabledata : tabledataSnark , search_input : input},

           cache: false,
           success: function(html) {
               $('#loaderSpin').html('');
               $("#result").html('');
               $("#result2").html(html);
           },
       });
   }

function search_result() {
    let input = document.getElementById('search-input').value
    input=input.toLowerCase();
    if ($('#table-one').attr("aria-controls") === "Data-table" && $('#table-one').attr("aria-selected") === "true") {
                        showDataForTabOne (10, 1, 0, input);
            }
            else if ($('#table-two').attr("aria-controls") === "Data-table-2" && $('#table-two').attr("aria-selected") === "true") {
                        alert("hello tab 2");
                        showDataForTabTwo (10, 1, 0 , input);
            }

}
    $(document).ready(function() {
        getRecords(10, 1);
        getRecordsForSnark(10, 1);

        $('input[type=search]').on('search', function () {
            if ($('#table-one').attr("aria-controls") === "Data-table" && $('#table-one').attr("aria-selected") === "true") {
                        showDataForTabOne (10, 1, 0);
            }
            else if ($('#table-two').attr("aria-controls") === "Data-table-2" && $('#table-two').attr("aria-selected") === "true") {
                        alert("hello tab 2");
                        showDataForTabTwo (10, 1, 0);
            }
        });
    });
</script>
</body>

</html>