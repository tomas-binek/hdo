<?php

function serve(int $httpCode, $content, $contentType = 'text/plain')
{
    http_response_code($httpCode);
    header('Content-Type: ' . $contentType);
    echo $content;
    die();

}

if (! array_key_exists('command'), $_GET)
    serve(400, "Missing 'command' argument");
else if (! array_key_exists('days'), $_GET)
    serve(400, "Missing 'days' argument");
else
    serve(200, ':-)')
