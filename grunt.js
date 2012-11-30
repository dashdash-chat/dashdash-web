module.exports = function(grunt) {

	grunt.initConfig({

		clean: [""],
		lint: {
			files: [
				"build/config.js", "app/**/*.js"
			]
		},
		concat: {
			dist: {
				src: [
					"assets/js/libs/almond.js",
					"dist/debug/templates.js",
					"dist/debug/require.js"
				],

				dest: "dist/debug/require.js",

				separator: ";"
			}
		},
		mincss: {
			"dist/release/index.css": [
				"dist/debug/index.css"
			]
		},
		styles: {
			// Out the concatenated contents of the following styles into the below
			// development file path.
			"dist/debug/index.css": {
				// Point this to where your `index.css` file is location.
				src: "assets/css/index.css",

				// The relative path to use for the @imports.
				paths: ["assets/css"],

				// Additional production-only stylesheets here.
				additional: []
			}
		},
		
		min: {
			"dist/release/require.js": [
				"dist/debug/require.js"
			]
		},
		watch: {
			stylus: {
				files: ["grunt.js", "assets/css/**/*.styl"],
				tasks: "stylus:dev"
			},
			less: {
				files: ["assets/css/less/*.less"],
				tasks: "less:main"
			}
		},

		less: {
			main: {
				files: {
					'static/css/vine.css' : 'static/css/less/vine/*.less'
				}
			}
		},
        copy: {
            dist: {
                files: {
                        "dist/release/img/": "assets/img/**"
                }
                , options: { "basePath" : "/", "flatten" : true }
            }
        },
	});

	grunt.registerTask('vine', 'less')
};
