location /robots.txt {
    add_header Content-Type text/plain;
    return 200 "User-agent: *\nDisallow: /\n";
}


location /yandex_0b55a167b1b836ed.html {
alias /etc/nginx/sites-enabled/ver.html;
}
