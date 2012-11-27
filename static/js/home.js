$(window).ready(function(){
	

	var kids = $('.vine-intro-convo').children('.vine-chat-bubble');
	//setTimeout(function(){ chatLeft(kids[0]); },1000);
	setTimeout(function(){ puff(kids[1]); },1000);
	setTimeout(function(){ puff(kids[2]); },2000);
	setTimeout(function(){ puff(kids[3]); },2500);
	setTimeout(function(){ puff(kids[4]); },3000);
	setTimeout(function(){ puff(kids[5]); },3250);

});


// try puff

function puff(el) {
	$(el).show('puff',{},500);	
}

function chatLeft(el) {
	$(el).show('slide',{},500);
}

function chatRight(el) {
	$(el).show('slide',{direction:'right'},500);
}