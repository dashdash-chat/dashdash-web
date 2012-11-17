$(window).ready(function(){
	

	var kids = $('.vine-intro-convo').children('.vine-chat-bubble');
	setTimeout(function(){ chatLeft(kids[0]); },1000);
	setTimeout(function(){ chatRight(kids[1]); },2000);
	setTimeout(function(){ chatLeft(kids[2]); },3000);
	setTimeout(function(){ chatRight(kids[3]); },3500);
	setTimeout(function(){ chatLeft(kids[4]); },4000);
	setTimeout(function(){ chatRight(kids[5]); },4250);

});

function chatLeft(el) {
	$(el).show('slide',{},500);
}

function chatRight(el) {
	$(el).show('slide',{direction:'right'},500);
}