package main

import (
	"github.com/gin-gonic/gin"
	"net/http"
	"encoding/json"
)

func ping(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func main() {
	r := gin.Default()
	r.GET("/ping", ping)
	r.Run()
}