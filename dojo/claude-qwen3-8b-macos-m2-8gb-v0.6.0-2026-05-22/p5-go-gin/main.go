package main

import (
	"fmt"
	"net/http"
	"github.com/gin-gonic/gin"
)

func pingHandler(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func main() {
	r := gin.Default()
	r.GET("/ping", pingHandler)
	r.Run(":8080")
}
