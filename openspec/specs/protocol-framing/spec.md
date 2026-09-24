# protocol-framing Specification

## Purpose

Define how the stdio Transport responds to input it cannot parse or cannot delimit, so
a malformed frame produces a protocol error or a clean exit rather than a crash.

## Requirements

### Requirement: Report an unparseable frame body and keep serving

When a frame's `Content-Length` header is valid and the full body arrives but the body
is not valid UTF-8 JSON, the server SHALL reply with a `PARSE_ERROR` (-32700) error
whose id is null, and SHALL continue reading the next frame. Requests already running
SHALL be unaffected. Framing SHALL remain byte-based: the declared length counts bytes
of the encoded body.

#### Scenario: Invalid JSON body
- **WHEN** a client sends a frame whose declared length matches its body but whose
  body is not valid JSON
- **THEN** the server replies with `PARSE_ERROR` and a null id
- **AND** a following valid request is answered normally

#### Scenario: Invalid JSON during a long query
- **WHEN** a long-running query is outstanding and the client sends an unparseable
  frame
- **THEN** the query later replies with its normal result

### Requirement: Stop cleanly when frames cannot be delimited

When the server cannot determine where a frame ends — the input ends before the
declared number of body bytes arrives, or a `Content-Length` header is not a
non-negative integer — the server SHALL log a diagnostic to stderr and shut down as it
does at end of input. It SHALL NOT write a traceback or any non-protocol text to
stdout, and SHALL NOT exit with an unhandled exception.

#### Scenario: Truncated body
- **WHEN** a client declares a longer `Content-Length` than it sends and then closes
  its input
- **THEN** the server logs a diagnostic on stderr and exits with a success status
- **AND** stdout contains only complete protocol frames

#### Scenario: Non-numeric length
- **WHEN** a client sends a `Content-Length` header whose value is not an integer
- **THEN** the server logs a diagnostic on stderr and exits without an unhandled
  exception
