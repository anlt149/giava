# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Copy go mod and sum files
COPY go.mod go.sum ./

# Download all dependencies
RUN go mod download

# Copy the source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o check_gold ./cmd/check_gold

# Final stage
FROM alpine:latest

# Install ca-certificates and tzdata for HTTPS requests and timezones
RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copy the pre-built binary file from the previous stage
COPY --from=builder /app/check_gold .

# Command to run the executable
CMD ["./check_gold"]
