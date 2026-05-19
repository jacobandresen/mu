package main

import (
	"github.com/gin-gonic/gin"
	"net/http"
	"encoding/json"
)

func ping(c *gin.Context) {
	response := map[string]string{"status": "ok"}
	jsonResponse, _ := json.Marshal(response)
	c.Data(http.StatusOK, "application/json", jsonResponse)
}

func main() {
	r := gin.Default()
	r.GET("/ping", ping)
	r.Run(":8080")
}