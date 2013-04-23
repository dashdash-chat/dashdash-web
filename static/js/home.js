$(window).ready(function(){
    
    var kids = $('.dashdash-intro-convo').children('.dashdash-chat-bubble');
    //setTimeout(function(){ chatLeft(kids[0]); },1000);
    setTimeout(function(){ puff(kids[1]); },1000);
    setTimeout(function(){ puff(kids[2]); },2000);
    setTimeout(function(){ puff(kids[3]); },2500);
    setTimeout(function(){ puff(kids[4]); },3000);
    setTimeout(function(){ puff(kids[5]); },3250);
    setTimeout(function(){ puff(kids[6]); },3500);
    
    // if a flash container is present then make it closable
    if( $('.flash-container').length )
    {
        $('.flash-container .close').click(function(){
            $('.flash-container').hide('blind',{'direction':'vertical'},'fast');
            return false;
        });
    }
    
    // if a list request link exists, then activate a form
    if( $('.list-request').length )
    {
        $('.list-request').click(function(){
            $('.list-request-container .hidden-form').toggle('blind',{'direction':'vertical'},'fast');
            return false;
        });
        $('.list-request-container .cancel-request').click(function(){
            $('.list-request-container input').val('');
            $('.list-request-container .hidden-form').hide('blind',{'direction':'vertical'},'fast');
            return false;
        });
        
        $('.list-request-container input').keyup(function(e){
            if(e.which == 13)
            {
                console.log('email entered', $('.list-request-container input').val() );
                var value = $('.list-request-container input').val();
                if( isEmail(value) )
                {
                    submitToList(value);
                    $('.list-request-container .hidden-form').hide('blind',{'direction':'vertical'},'slow');
                    $('.header-banner').effect('highlight',{},750);
                    $('.list-request').remove();
                    $('.list-request-container').prepend('<p>Thanks! Keep an eye on your inbox</p>');
                }
            }
        });
    }

});

function puff(el) {
    $(el).show('puff',{},500);
}

function isEmail(email)
{
    var regex = /^([a-zA-Z0-9_\.\-\+])+\@(([a-zA-Z0-9\-])+\.)+([a-zA-Z0-9]{2,4})+$/;
    return regex.test(email);
}

function submitToList(email)
{
    $.ajax({
        type: 'POST',
        url: 'https://docs.google.com/spreadsheet/formResponse?formkey=dEduRlNBODVMMjBqZE8xdmZTYWc3aHc6MQ&amp;embedded=true&amp;ifq',
        data: {
          'entry.0.single': email 
        }
    });
}