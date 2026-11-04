/* MIT licensed, dependency-free MCP onboarding status. No files, network or paid calls. */
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define LIMIT 65536
#define TOKENS 4096
struct token { int start, end, kind; };
struct parser { const char *s; int n, p, count; struct token tokens[TOKENS]; };
static void ws(struct parser *p) { while(p->p<p->n && strchr(" \t\r\n",p->s[p->p]) && p->s[p->p]) p->p++; }
static int value(struct parser *p, int depth);
static int string(struct parser *p) {
    if(p->p>=p->n || p->s[p->p++]!='"') return 0;
    while(p->p<p->n) {
        unsigned char c=p->s[p->p++];
        if(c=='"') return 1;
        if(c<32) return 0;
        if(c=='\\') {
            if(p->p>=p->n) return 0;
            c=p->s[p->p++];
            if(c=='u') { for(int i=0;i<4;i++) if(p->p>=p->n || !isxdigit((unsigned char)p->s[p->p++])) return 0; }
            else if(!strchr("\"\\/bfnrt",c) || !c) return 0;
        }
    }
    return 0;
}
static int value(struct parser *p, int depth) {
    ws(p); if(depth>64 || p->p>=p->n || p->count>=TOKENS) return -1;
    int index=p->count++; struct token *t=&p->tokens[index]; t->start=p->p;
    char c=p->s[p->p]; t->kind=c;
    if(c=='"') { if(!string(p)) return -1; }
    else if(c=='{' || c=='[') {
        p->p++; ws(p); char close=c=='{'?'}':']';
        if(p->p<p->n && p->s[p->p]==close) p->p++;
        else for(;;) {
            if(c=='{') {
                if(p->count>=TOKENS) return -1;
                int k=p->count++; p->tokens[k]=(struct token){p->p,0,'"'};
                if(!string(p)) return -1;
                p->tokens[k].end=p->p; ws(p);
                if(p->p>=p->n || p->s[p->p++]!=':') return -1;
            }
            if(value(p,depth+1)<0) return -1;
            ws(p); if(p->p>=p->n) return -1;
            char next=p->s[p->p++]; if(next==close) break;
            if(next!=',') return -1;
            ws(p);
        }
    } else if(c=='-' || isdigit((unsigned char)c)) {
        t->kind='n'; if(c=='-') p->p++;
        if(p->p>=p->n) return -1;
        if(p->s[p->p]=='0') p->p++;
        else { if(p->s[p->p]<'1'||p->s[p->p]>'9') return -1; while(p->p<p->n&&isdigit((unsigned char)p->s[p->p]))p->p++; }
        if(p->p<p->n&&p->s[p->p]=='.') { p->p++; int start=p->p; while(p->p<p->n&&isdigit((unsigned char)p->s[p->p]))p->p++; if(start==p->p)return -1; }
        if(p->p<p->n&&(p->s[p->p]=='e'||p->s[p->p]=='E')) { p->p++; if(p->p<p->n&&(p->s[p->p]=='+'||p->s[p->p]=='-'))p->p++; int start=p->p; while(p->p<p->n&&isdigit((unsigned char)p->s[p->p]))p->p++; if(start==p->p)return -1; }
    } else {
        const char *word=c=='t'?"true":c=='f'?"false":c=='n'?"null":NULL;
        if(!word || p->p+(int)strlen(word)>p->n || memcmp(p->s+p->p,word,strlen(word))) return -1;
        t->kind=c=='n'?'0':'b'; p->p+=(int)strlen(word);
    }
    t->end=p->p; return index;
}
static int equal(struct parser *p, int i, const char *s) {
    if(i<0||p->tokens[i].kind!='"')return 0;
    int n=p->tokens[i].end-p->tokens[i].start-2;
    return n==(int)strlen(s)&&!memcmp(p->s+p->tokens[i].start+1,s,(size_t)n);
}
static int field(struct parser *p,int object,const char *key) {
    if(object<0||p->tokens[object].kind!='{')return -1;
    int i=object+1;
    while(i<p->count&&p->tokens[i].start<p->tokens[object].end) {
        int k=i++,v=i; if(v>=p->count)return -1;
        if(equal(p,k,key))return v;
        int end=p->tokens[v].end; i++;
        while(i<p->count&&p->tokens[i].start<end)i++;
    }
    return -1;
}
static void response(struct parser *p,int id,const char *result,int error) {
    printf("{\"jsonrpc\":\"2.0\",\"id\":");
    if(id>=0&&(p->tokens[id].kind=='"'||p->tokens[id].kind=='n'||p->tokens[id].kind=='0'))
        printf("%.*s",p->tokens[id].end-p->tokens[id].start,p->s+p->tokens[id].start);
    else printf("null");
    if(error)printf(",\"error\":{\"code\":%d,\"message\":\"%s\"}}\n",error,result);
    else printf(",\"result\":%s}\n",result);
    fflush(stdout);
}
static const char *setup_response = "{\"content\":[{\"type\":\"text\",\"text\":\"\\ub85c\\uceec \\uae30\\uc5b5 \\ub7f0\\ud0c0\\uc784\\uc758 \\ucd08\\uae30 \\uc124\\uc815\\uc774 \\uc544\\uc9c1 \\ub05d\\ub098\\uc9c0 \\uc54a\\uc558\\uc2b5\\ub2c8\\ub2e4. \\ub9c8\\ucf13 \\uba85\\ub839\\uc740 \\uc5f0\\uacb0 \\ud50c\\ub7ec\\uadf8\\uc778\\ub9cc \\uc124\\uce58\\ud569\\ub2c8\\ub2e4.\\nDocker Desktop\\uc744 \\uc2e4\\ud589\\ud558\\uace0, \\ud648 \\ud3f4\\ub354(~)\\uac00 \\uc544\\ub2cc \\uc2e4\\uc81c \\uc791\\uc5c5 \\ud504\\ub85c\\uc81d\\ud2b8\\uc758 \\ud130\\ubbf8\\ub110\\uc5d0\\uc11c \\uc9c4\\ud589\\ud558\\uc138\\uc694.\\ncurl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.4/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh\\nbash /tmp/agents-memory-mcp-install.sh --client omp --project \\\"$PWD\\\"\\nJev \\ud0a4\\ub294 \\ud654\\uba74\\uc5d0 \\ud45c\\uc2dc\\ub418\\uc9c0 \\uc54a\\uc2b5\\ub2c8\\ub2e4. \\uc785\\ub825 \\ud6c4 Enter\\ub85c \\ud655\\uc815\\ud558\\uace0 \\uc124\\uce58 \\uc644\\ub8cc \\uba54\\uc2dc\\uc9c0\\ub97c \\uae30\\ub2e4\\ub9ac\\uc138\\uc694. \\uc774\\ubbf8 \\uc124\\uce58 \\uc911\\uc774\\uba74 \\uc911\\ubcf5 \\uc2e4\\ud589\\ud558\\uc9c0 \\ub9c8\\uc138\\uc694.\\n\\uc124\\uce58\\uac00 \\ub05d\\ub098\\uba74 OMP\\uc5d0\\uc11c /mcp reload\\ub97c \\uc2e4\\ud589\\ud558\\uc138\\uc694. \\ud604\\uc7ac \\uba54\\ubaa8\\ub9ac \\ub3c4\\uad6c\\ub294 \\uc900\\ube44\\ub418\\uc9c0 \\uc54a\\uc558\\uc2b5\\ub2c8\\ub2e4.\\n\\uc774 \\uc548\\ub0b4 \\ub3c4\\uad6c\\ub294 \\uc124\\uce58, \\uc774\\ub825 \\uc77d\\uae30, \\ubaa8\\ub378 \\ud638\\ucd9c\\uc744 \\uc218\\ud589\\ud558\\uc9c0 \\uc54a\\uc2b5\\ub2c8\\ub2e4.\"}],\"structuredContent\":{\"ready\":false,\"state\":\"runtime_not_installed\",\"setupRequired\":true,\"version\":\"1.0.4\"},\"isError\":false}";
static int utf8(const unsigned char *s,int n) {
    int i=0;
    while(i<n) {
        unsigned int c=s[i++], cp=0, need=0, minimum=0;
        if(c<128)continue;
        if(c>=0xc2&&c<=0xdf){need=1;cp=c&31;minimum=128;}
        else if(c>=0xe0&&c<=0xef){need=2;cp=c&15;minimum=2048;}
        else if(c>=0xf0&&c<=0xf4){need=3;cp=c&7;minimum=65536;}
        else return 0;
        if(i+(int)need>n)return 0;
        while(need--){unsigned int b=s[i++];if((b&0xc0)!=0x80)return 0;cp=(cp<<6)|(b&63);}
        if(cp<minimum||cp>0x10ffff||(cp>=0xd800&&cp<=0xdfff))return 0;
    }
    return 1;
}
static void handle(char *line,int size) {
    struct parser p={.s=line,.n=size};
    if(!utf8((const unsigned char*)line,size)){response(&p,-1,"Invalid UTF-8",-32700);return;}
    int root=value(&p,0);ws(&p);
    if(root<0||p.p!=size){response(&p,-1,"Invalid JSON",-32700);return;}
    int id=field(&p,root,"id"),method=field(&p,root,"method"),params=field(&p,root,"params");
    if(root!=0||p.tokens[root].kind!='{'||!equal(&p,field(&p,root,"jsonrpc"),"2.0")||method<0||p.tokens[method].kind!='"') {response(&p,id,"Invalid request",-32600);return;}
    if(id<0)return;
    if(p.tokens[id].kind!='"'&&p.tokens[id].kind!='n'){response(&p,-1,"Invalid request id",-32600);return;}
    if(equal(&p,method,"initialize")) {
        const char *versions[]={"2025-11-25","2025-06-18","2025-03-26","2024-11-05"};
        const char *protocol="2025-03-26";
        int requested=field(&p,params,"protocolVersion");
        for(int i=0;i<4;i++)if(equal(&p,requested,versions[i]))protocol=versions[i];
        char result[768];snprintf(result,sizeof result,"{\"protocolVersion\":\"%s\",\"capabilities\":{\"tools\":{}},\"serverInfo\":{\"name\":\"agents-memory-local-setup\",\"version\":\"1.0.4\"},\"instructions\":\"Local memory runtime is not installed. This connection only reports setup status; memory is not ready. Call setup_status for terminal setup instructions. Do not claim that memory has been configured.\"}",protocol);
        response(&p,id,result,0);
    } else if(equal(&p,method,"ping"))response(&p,id,"{}",0);
    else if(equal(&p,method,"tools/list"))response(&p,id,"{\"tools\":[{\"name\":\"setup_status\",\"description\":\"Show why local memory is not ready and how to complete setup. Does not install anything, read history, or call a model.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}}]}",0);
    else if(equal(&p,method,"tools/call")) {
        if(!equal(&p,field(&p,params,"name"),"setup_status")){response(&p,id,"Unknown setup tool",-32602);return;}
        response(&p,id,setup_response,0);
    } else response(&p,id,"Method not found",-32601);
}
int main(void) {
    char line[LIMIT+1];setvbuf(stdout,NULL,_IOLBF,0);
    for(;;) {
        int size=0,overflow=0,c;
        while((c=getchar())!=EOF&&c!='\n') {if(size<LIMIT)line[size++]=(char)c;else overflow=1;}
        if(c==EOF&&!size&&!overflow)break;
        if(overflow){struct parser p={0};response(&p,-1,"Request too large",-32700);}
        else if(size)handle(line,size);
        if(c==EOF)break;
    }
    return 0;
}
