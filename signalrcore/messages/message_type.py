"""    # noqa E501

| Message Name          | Sender         | Description                                                                                                                    |
| ------------------    | -------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `HandshakeRequest`    | Client         | Sent by the client to agree on the message format.                                                                            |
| `HandshakeResponse`   | Server         | Sent by the server as an acknowledgment of the previous `HandshakeRequest` message. Contains an error if the handshake failed. |
| `Close`               | Callee, Caller | Sent by the server when a connection is closed. Contains an error if the connection was closed because of an error. Sent by the client when it's closing the connection, unlikely to contain an error. |
| `Invocation`          | Caller         | Indicates a request to invoke a particular method (the Target) with provided Arguments on the remote endpoint.                 |
| `StreamInvocation`    | Caller         | Indicates a request to invoke a streaming method (the Target) with provided Arguments on the remote endpoint.                  |
| `StreamItem`          | Callee, Caller | Indicates individual items of streamed response data from a previous `StreamInvocation` message or streamed uploads from an invocation with streamIds.                               |
| `Completion`          | Callee, Caller | Indicates a previous `Invocation` or `StreamInvocation` has completed or a stream in an `Invocation` or `StreamInvocation` has completed. Contains an error if the invocation concluded with an error or the result of a non-streaming method invocation. The result will be absent for `void` methods. In case of streaming invocations no further `StreamItem` messages will be received. |
| `CancelInvocation`    | Caller         | Sent by the client to cancel a streaming invocation on the server.                                                             |
| `Ping`                | Caller, Callee | Sent by either party to check if the connection is active.                                                                     |
| `Ack`                 | Caller, Callee | Sent by either party to acknowledge that messages have been received up to the provided sequence ID.                                                                |
| `Sequence`            | Caller, Callee | Sent by either party as the first message when a connection reconnects. Specifies what sequence ID they will start sending messages starting at. Duplicate messages are possible to receive and should be ignored.                                                                    |

"""
from enum import Enum


class MessageType(Enum):
    invocation = 1
    stream_item = 2
    completion = 3
    stream_invocation = 4
    cancel_invocation = 5
    ping = 6
    close = 7
    ack = 8
    sequence = 9
    invocation_binding_failure = -1
