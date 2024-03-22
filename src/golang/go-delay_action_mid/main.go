/**
* © 2024 Daniil Sokolov <daniil.sokolov@webcloudai.com>
* MIT License
 */
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"strings"
	"time"

	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/google/uuid"
)

func readFileContents(filePath string) ([]byte, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening file: %w", err)
	}
	defer file.Close()

	contents, err := ioutil.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("error reading file contents: %w", err)
	}

	return contents, nil
}

func HandleRequest(ctx context.Context, event events.APIGatewayProxyRequest) (events.APIGatewayProxyResponse, error) {
	// pause execution for 300ms
	time.Sleep(300 * time.Millisecond)
	// Serialize the event to JSON to use as the object content
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error marshaling event to JSON: %w", err)
	}

	// Load the Shared AWS Configuration (~/.aws/config)
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error loading AWS configuration: %w", err)
	}

	// Extract the bucket name from stage variables
	bucketName, exists := event.StageVariables["testBucketName"]
	if !exists {
		return events.APIGatewayProxyResponse{
			StatusCode: 400,
			Body:       "Bucket name not provided in stage variables",
		}, nil
	}

	// Read the large_mock.json file just to make the package bigger
	filePath := "assets/large_mock.json"
	fileContents, err := readFileContents(filePath)
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error reading JSON file: %w", err)
	}

	// Use a map[string]interface{} to handle the dynamic JSON structure
	var jsonData map[string]interface{}
	if err := json.Unmarshal(fileContents, &jsonData); err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error parsing JSON file: %w", err)
	}

	// Optionally modify the jsonData map here

	// Serialize the map back to JSON (we don't need back serialization as we don't do that in Python and TS)
	// updatedJSON, err := json.Marshal(jsonData)
	// if err != nil {
	//     return events.APIGatewayProxyResponse{}, fmt.Errorf("error serializing JSON: %w", err)
	// }

	// Create an Amazon S3 service client
	client := s3.NewFromConfig(cfg)
	// Generate a unique UUID for the S3 object key
	objectKey := uuid.NewString()

	// Putting the serialized event into the S3 bucket as an object
	_, err = client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
		Body:   strings.NewReader(string(eventJSON)),
	})
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error putting object into S3 bucket: %w", err)
	}

	// wait a little
	time.Sleep(100 * time.Millisecond)

	// Deleting the object from the S3 bucket (optional based on your use case)
	_, err = client.DeleteObject(ctx, &s3.DeleteObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
	})
	if err != nil {
		return events.APIGatewayProxyResponse{}, fmt.Errorf("error deleting object from S3 bucket: %w", err)
	}

	// Returning the original event JSON as the response body
	return events.APIGatewayProxyResponse{
		StatusCode: 200,
		Body:       string(eventJSON),
	}, nil
}

func main() {
	lambda.Start(HandleRequest)
}
