$(function(){
    $(".previewurl" ).each(function(index) {
        //gets each class and should add an onclick with "store" attr as link to audio player
        
        //console.log(index + ": " + $(this).children("a").attr("store"));
        
        //i thought $(this).children("a") was the link?? why doesn't the next line work
        //JK FIGURED IT OUT YOU CAN'T USE .click, YOU HAVE TO USE EVENT DELEGATION i.e. .on(click)
        $(this).children("a").on('click',  function() {
            
            //if the player that is playing isn't of the current link
            //so a new player should overwrite the first
            if ($("#previewplayer").attr("src") != $(this).attr("store")){
                //if other audio players open, close. open new one for this song.
                //also set all text to "Preview"
                if($("#previewplayer").length) { //try this without '!=0' - boolean zen?
                    console.log("removing player...")
                    //it already exists/is open
                    $("#previewplayer").remove();
                    //set all to "Preview"
                    $(".preview").text("Preview")
                }
                

                //what if on end of audio object, change its container text back to "Preview"

                //$('#playerplaceholder').empty();
                //create new one
                //console.log($(this).attr("obj"))
                player = $('<audio>').attr({
                    'src': $(this).attr("store"),
                    'id': 'previewplayer',
                    'autoplay':'autoplay',
                    'controls':'true',
                    'controlsList':"nodownload",
                    'volume':0.5
                });

                console.log("creating player...");
                console.log(player);
                //append player somewhere
                //for now, player placeholder
                $('#playerplaceholder').append(player);

                //change text to Pause and then change function to pause
                $(this).text("Cancel");
            
            //if the player matches the current link it should be stopped
            } else {
                console.log("removing player...")
                $("#previewplayer").remove();
                $(this).text("Preview")
            }
        
        });
    });
})