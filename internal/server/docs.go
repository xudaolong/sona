package server

import (
	"context"
	"fmt"
	"net/http"

	"github.com/danielgtaylor/huma/v2"
	"github.com/danielgtaylor/huma/v2/adapters/humago"
)

type docsTranscriptionForm struct {
	File           huma.FormFile `form:"file"`
	Language       string        `form:"language"`
	Prompt         string        `form:"prompt"`
	DetectLanguage string        `form:"detect_language"`
	EnhanceAudio   string        `form:"enhance_audio"`
	Model          string        `form:"model"`
}

type docsTranscriptionInput struct {
	RawBody huma.MultipartFormFiles[docsTranscriptionForm]
}

type docsTranscriptionOutput struct {
	Body struct {
		Text string `json:"text"`
	}
}

type docsModelsOutput struct {
	Body map[string]any
}

func (s *Server) registerDocsRoutes(mux *http.ServeMux) {
	docsMux := http.NewServeMux()
	config := huma.DefaultConfig("Sona API", "dev")
	config.DocsPath = ""
	api := humago.New(docsMux, config)

	huma.Register(api, huma.Operation{
		Method:      http.MethodPost,
		Path:        "/v1/audio/transcriptions",
		OperationID: "createTranscription",
		Summary:     "Create transcription",
	}, func(context.Context, *docsTranscriptionInput) (*docsTranscriptionOutput, error) {
		return nil, huma.Error501NotImplemented("spec-only operation")
	})

	huma.Register(api, huma.Operation{
		Method:      http.MethodGet,
		Path:        "/v1/models",
		OperationID: "listModels",
		Summary:     "List loaded models",
	}, func(context.Context, *struct{}) (*docsModelsOutput, error) {
		return nil, huma.Error501NotImplemented("spec-only operation")
	})

	mux.HandleFunc("GET /docs", serveSwaggerUI)
	mux.HandleFunc("GET /docs/", redirectDocs)
	mux.Handle("/openapi.json", docsMux)
	mux.Handle("/openapi.yaml", docsMux)
	mux.Handle("/openapi-3.0.json", docsMux)
	mux.Handle("/openapi-3.0.yaml", docsMux)
	mux.Handle("/schemas/", docsMux)
}

func redirectDocs(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "/docs", http.StatusTemporaryRedirect)
}

func serveSwaggerUI(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sona API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
    <style>
      html, body { margin: 0; padding: 0; }
      #swagger-ui { max-width: 1200px; margin: 0 auto; }
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
    <script>
      SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayRequestDuration: true
      });
    </script>
  </body>
</html>`)
}
