Development Setup
----------
0. Install nginx on the same machine as ejabberd
  * TODO
0. Optionally set up the vine.im home page form
  * TODO
0. Install necessary Perl modules
  * `sudo yum install cpan`
  * `cpan`
  * `o conf urllist`  # Make sure there are valid mirrors, and if not, try adding the following
  * `o conf urllist push http://cpan.strawberryperl.com/`
  * `o conf commit`
  * Control-d to leave the cpan prompt
  * `sudo cpan Locale::Maketext::Fuzzy`  # And repeat for any other necessary modules, noting that error messages like "Can't locate Locale/Maketext/Fuzzy.pm in @INC" mean you should try commands like the one mentioned
0. Fetch, configure, and install JWChat
  * `git clone git@github.com:lehrblogger/vine-jwchat.git jwchat`
  * `sudo sh install.sh [vine.im or dev.vine.im] [username] [password] [random string for URL] [optional debug flag]`
