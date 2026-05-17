package main

import (
	"github.com/gin-gonic/gin"
	"net/http"
)

func ping(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func main() {
	router := gin.Default()
	router.GET("/ping", ping)
	err := router.Run(":8080")
	if err != nil {
		panic("failed to start server: " + err.Error())
	}
}