$(window).ready(function(){
    $('.instructions h1 a').click(function(){
        var name = this.name;
        $('.instructions h1 a[name!=' +  name + ']').removeClass('selected');
        $('.instructions h1 a[name=' +  name + ']').addClass('selected');
        $('.instructions ol[name!=' +  name + ']').removeClass('selected');
        $('.instructions ol[name=' +  name + ']').addClass('selected');
        return false;
    });
});
