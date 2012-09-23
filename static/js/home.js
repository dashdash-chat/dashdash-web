$(window).ready(function(){
	
	setTimeout(function(){ hello(); },1000);
	setTimeout(function(){ vineIs(); },2000);
	setTimeout(function(){ youCanSee(); },3000);
	//setTimeout(function(){ bounceSignIn(); },6000);


});

function hello()
{
	var bubble = $('.vine-intro-convo').children('.vine-chat-bubble')[0];
	$(bubble).show('slide',{},500);
}

function vineIs()
{
	var bubble = $('.vine-intro-convo').children('.vine-chat-bubble')[1];
	$(bubble).show('slide',{direction:'right'},500);
}

function youCanSee()
{
	var bubble = $('.vine-intro-convo').children('.vine-chat-bubble')[2];
	$(bubble).show('slide',{direction:'left'},500);
}

function bounceSignIn()
{
	$('.vine-sign-in').effect('bounce',{times:2,direction:'horizontal', distance:5},500)
}