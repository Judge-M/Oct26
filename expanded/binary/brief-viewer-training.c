/* Harmless static-analysis surrogate. No files, processes, persistence or network IO. */
#include <stdio.h>
const char *destination = "198.51.100.77";
const char *upload_path = "/upload";
const char *task_label = "BriefSync";
const char *cache_path = "C:/Temp/move-cache.txt";
const char *classify_version(int version) {
    if (version == 3) return "cached v3";
    return "other version";
}
int main(void) {
    puts("Fictional Silent Ridge static-analysis training surrogate. No network behavior.");
    puts(classify_version(3));
    return 0;
}
