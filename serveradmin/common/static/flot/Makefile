all: jquery.flot.min.js

jquery.flot.min.js: jquery.flot.js jquery.flot.stack.js
	yui-compressor jquery.flot.js > $@
	echo -n "\n\n" >> $@
	yui-compressor jquery.flot.stack.js >> $@
