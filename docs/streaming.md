---
layout: default
title: Streaming
nav_order: 4
---

# Streaming
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Server-to-Client Streaming

Use `hub_connection.stream()` to subscribe to a server-side streaming method. The subscription object accepts three callbacks:

| Callback | Description |
|----------|-------------|
| `next` | Called for each item streamed from the server |
| `complete` | Called when the stream ends successfully |
| `error` | Called if the stream encounters an error |

```python
hub_connection.stream(
    "Counter",
    [len(self.items), 500]  # method arguments
).subscribe({
    "next": self.on_next,
    "complete": self.on_complete,
    "error": self.on_error
})
```

### Example Callbacks

```python
def on_next(self, value):
    print(f"Received: {value}")

def on_complete(self):
    print("Stream complete")

def on_error(self, error):
    print(f"Stream error: {error}")
```

---

## Client-to-Server Streaming

Use a `Subject` to stream data from the client to the server:

```python
from signalrcore.subject import Subject

subject = Subject()

# Start the streaming invocation
hub_connection.send("UploadStream", subject)

# Send items during the stream
subject.next(str(iteration))

# Signal end of stream
subject.complete()
```

### Full Client Streaming Example

```python
from signalrcore.subject import Subject
import time

subject = Subject()
hub_connection.send("UploadStream", subject)

for i in range(10):
    subject.next(str(i))
    time.sleep(0.5)

subject.complete()
```

---

## Notes

- Server-to-client streaming uses the `IAsyncEnumerable<T>` or `ChannelReader<T>` pattern on the .NET server side.
- Client-to-server streaming sends items incrementally until `subject.complete()` is called.
- More examples are available in the [tests folder](https://github.com/mandrewcito/signalrcore/tree/master/test/examples).
