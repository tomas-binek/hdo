<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

#die(posix_getpwuid(posix_geteuid())['name']);

$parserScript = $_SERVER['DOCUMENT_ROOT'] . "/hdo-data.py";
$cacheDir = $_SERVER['DOCUMENT_ROOT'] . "/cache";

function serve(int $httpCode, $content, $contentType = 'text/plain')
{
    http_response_code($httpCode);
    header('Content-Type: ' . $contentType);
    echo $content;
    die();
}

function getCacheFilePath(int $command, int $days)
{
    global $cacheDir;
    return $cacheDir . '/command:'. $command . ',since:' . date('Y-m-d') . ',days:' . $days . '.txt';
}

function isoToUnixTimestamp (string $isoTimestamp)
{
    $dateObject = new DateTime($isoTimestamp);
    return $dateObject->format('U');
}

if (! array_key_exists('command', $_GET))
    serve(400, "Missing 'command' argument");
else if (! array_key_exists('days', $_GET))
    serve(400, "Missing 'days' argument");
else
{
    $arg_command = intval($_GET['command']);
    $arg_days = intval($_GET['days']);
    $arg_unixTime = array_key_exists('unixTime', $_GET);

    $cacheFile = getCacheFilePath($arg_command, $arg_days);

    if (! file_exists($cacheFile))
    {
        exec("/usr/bin/python3 $parserScript $arg_command $arg_days", $pythonOutput, $pythonExitCode);

        //print_r($_SERVER);
        if ($pythonExitCode != 0)
            serve(500, "Python died (" . $pythonExitCode . ")");
        else
        {
            file_put_contents(
                $cacheFile,
                json_encode(
                    array_map(
                        function ($line) use ($arg_unixTime)
                        {
                            $lineAsObject = new stdClass();
                            list($lineAsObject->start, $lineAsObject->end, $lineAsObject->tariff) = explode(' ', $line);
                            return $lineAsObject;
                        },
                        $pythonOutput
                    )
                )
            );
        }
    }

    $data = file_get_contents($cacheFile);

    if ($arg_unixTime)
    {
        $data = json_encode(
            array_map(
                function ($record)
                {
                    $record->start = intval(isoToUnixTimestamp($record->start));
                    $record->end = intval(isoToUnixTimestamp($record->end));

                    return $record;
                },
                json_decode($data)
            )
        );
    }

    serve(200, $data, 'application/json');
}
