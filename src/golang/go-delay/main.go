
package main

import (
	"context"
    "encoding/json"
	"fmt"
    "time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func handleRequest(ctx context.Context, event events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
    // pause execution for 300ms
	time.Sleep(300 * time.Millisecond)
    // Serialize the event to JSON to use as the object content
    eventJSON, err := json.Marshal(event)
    if err != nil {
        return events.APIGatewayProxyResponse{}, fmt.Errorf("error marshaling event to JSON: %w", err)
    }

	return events.APIGatewayProxyResponse{Body: string(eventJSON), StatusCode: 200}, nil
}

func main() {
	lambda.Start(handleRequest)
}