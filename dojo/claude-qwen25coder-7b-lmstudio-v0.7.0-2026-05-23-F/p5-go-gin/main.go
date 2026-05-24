package main

import (
	"encoding/json"
	"net/http"
	"github.com/gin-gonic/gin"
	"os"
)

func main() {
	r := gin.Default()
	port := ":8080"
	r.GET("/ping", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})
}
